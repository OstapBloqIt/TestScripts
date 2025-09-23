#!/usr/bin/env python3
# Fixed camera app matching working pattern structure exactly

import os
import gi
import sys
import time
import subprocess
import glob
import re

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gst

# Force Wayland backend - EXACTLY like working pattern
Gdk.set_allowed_backends("wayland")

_prev_total = 0
_prev_idle = 0

def read_cpu_percent():
    global _prev_total, _prev_idle
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        parts = [float(x) for x in line.split()[1:8]]
        user, nice, system, idle, iowait, irq, softirq = parts
        idle_all = idle + iowait
        non_idle = user + nice + system + irq + softirq
        total = idle_all + non_idle
        if _prev_total == 0:
            _prev_total, _prev_idle = total, idle_all
            return 0.0
        totald = total - _prev_total
        idled = idle_all - _prev_idle
        _prev_total, _prev_idle = total, idle_all
        if totald <= 0:
            return 0.0
        return max(0.0, min(100.0, (totald - idled) * 100.0 / totald))
    except Exception:
        return 0.0

def read_mem_percent():
    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                key, val = line.split(':', 1)
                meminfo[key.strip()] = int(val.strip().split()[0])
        total = meminfo.get('MemTotal', 1)
        free = meminfo.get('MemFree', 0) + meminfo.get('Buffers', 0) + meminfo.get('Cached', 0)
        used = max(0, total - free)
        return used * 100.0 / total
    except Exception:
        return 0.0

def get_video_devices():
    devices = []
    for device_path in glob.glob('/dev/video*'):
        device_num = int(re.findall(r'\d+', device_path)[-1])
        if device_num >= 2:
            try:
                with open(device_path, 'rb') as f:
                    devices.append(device_path)
            except (PermissionError, OSError):
                pass
    return sorted(devices) if devices else ['/dev/video2']

def get_device_formats(device_path):
    try:
        result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            formats = []
            for line in result.stdout.split('\n'):
                match = re.search(r"\[(\d+)\]:\s+'([^']+)'\s+\(([^)]+)\)", line)
                if match:
                    code, desc = match.group(2), match.group(3)
                    formats.append((code, f"{code} ({desc})"))
            return formats if formats else [('MJPG', 'MJPG (Motion-JPEG)')]
    except:
        pass
    return [('MJPG', 'MJPG (Motion-JPEG)'), ('YUYV', 'YUYV (YUV 4:2:2)')]

class CameraWindow(Gtk.Window):
    def __init__(self):
        # EXACT same init pattern as working app
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("USB Camera Touch Viewer")
        self.connect("destroy", Gtk.main_quit)

        # Get devices first (before GStreamer)
        self.video_devices = get_video_devices()
        self.device = self.video_devices[0]
        self.current_format = 'MJPG'
        self.available_formats = get_device_formats(self.device)
        self.width, self.height, self.fps = 640, 480, 30
        self.paused = False
        self.pipeline = None

        self.res_options = [(320, 240), (640, 480), (800, 600), (1280, 720), (1920, 1080)]

        self.setup_ui()

        # Initialize GStreamer AFTER UI setup
        Gst.init(None)

        # Add timeout for updates
        GLib.timeout_add(500, self.update_usage)
        GLib.timeout_add(100, self.delayed_init)  # Delayed pipeline setup

    def delayed_init(self):
        """Initialize pipeline after window is shown"""
        self.build_pipeline()
        return False  # Run only once

    def setup_ui(self):
        # Main container
        vbox = Gtk.VBox(spacing=8)
        vbox.set_property("margin", 12)
        self.add(vbox)

        # Video area placeholder
        self.video_area = Gtk.EventBox()
        self.video_area.set_size_request(640, 480)
        label = Gtk.Label(label="Camera will appear here...")
        self.video_area.add(label)
        vbox.pack_start(self.video_area, True, True, 0)

        # Controls
        controls = Gtk.HBox(spacing=8)
        vbox.pack_start(controls, False, False, 0)

        # Device selector
        controls.pack_start(Gtk.Label(label="Device:"), False, False, 0)
        self.device_combo = Gtk.ComboBoxText()
        for device in self.video_devices:
            self.device_combo.append_text(device)
        self.device_combo.set_active(0)
        self.device_combo.connect("changed", self.on_device_changed)
        controls.pack_start(self.device_combo, False, False, 0)

        # Format selector
        controls.pack_start(Gtk.Label(label="Format:"), False, False, 0)
        self.format_combo = Gtk.ComboBoxText()
        for code, desc in self.available_formats:
            self.format_combo.append_text(desc)
        self.format_combo.set_active(0)
        self.format_combo.connect("changed", self.on_format_changed)
        controls.pack_start(self.format_combo, False, False, 0)

        # Resolution
        controls.pack_start(Gtk.Label(label="Res:"), False, False, 0)
        self.res_combo = Gtk.ComboBoxText()
        for w, h in self.res_options:
            self.res_combo.append_text(f"{w}x{h}")
        self.res_combo.set_active(1)  # 640x480
        self.res_combo.connect("changed", self.on_resolution_changed)
        controls.pack_start(self.res_combo, False, False, 0)

        # FPS
        controls.pack_start(Gtk.Label(label="FPS:"), False, False, 0)
        self.fps_scale = Gtk.HScale()
        self.fps_scale.set_range(1, 60)
        self.fps_scale.set_value(30)
        self.fps_scale.set_digits(0)
        self.fps_scale.set_size_request(100, -1)
        self.fps_scale.connect("value-changed", self.on_fps_changed)
        controls.pack_start(self.fps_scale, False, False, 0)

        # Buttons
        self.start_btn = Gtk.Button(label="Start")
        self.start_btn.connect("clicked", self.on_start_stop)
        controls.pack_start(self.start_btn, False, False, 0)

        self.exit_btn = Gtk.Button(label="Exit")
        self.exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        controls.pack_start(self.exit_btn, False, False, 0)

        # Usage label
        self.usage_label = Gtk.Label(label="CPU 0% | RAM 0%")
        controls.pack_start(self.usage_label, False, False, 0)

        # Show all and THEN fullscreen - like working pattern
        self.show_all()
        self.fullscreen()

    def on_device_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0:
            self.device = self.video_devices[idx]
            self.available_formats = get_device_formats(self.device)
            self.format_combo.remove_all()
            for code, desc in self.available_formats:
                self.format_combo.append_text(desc)
            self.format_combo.set_active(0)

    def on_format_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0 and idx < len(self.available_formats):
            self.current_format = self.available_formats[idx][0]

    def on_resolution_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0:
            self.width, self.height = self.res_options[idx]

    def on_fps_changed(self, scale):
        self.fps = int(scale.get_value())

    def on_start_stop(self, btn):
        if self.pipeline:
            self.stop_pipeline()
            self.start_btn.set_label("Start")
        else:
            self.build_pipeline()
            self.start_btn.set_label("Stop")

    def build_pipeline(self):
        if self.pipeline:
            self.stop_pipeline()

        try:
            # Simple pipeline for testing
            pipeline_str = f"v4l2src device={self.device} ! videoconvert ! autovideosink"
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)
            print(f"Started pipeline: {pipeline_str}")
        except Exception as e:
            print(f"Pipeline error: {e}")
            self.pipeline = None

    def stop_pipeline(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

    def update_usage(self):
        cpu = read_cpu_percent()
        mem = read_mem_percent()
        self.usage_label.set_text(f"CPU {cpu:.0f}% | RAM {mem:.0f}%")
        return True

if __name__ == "__main__":
    # EXACT same pattern as working app
    CameraWindow()
    Gtk.main()