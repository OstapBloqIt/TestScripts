#!/usr/bin/env python3
# complete_camera.py - Full featured camera app with all controls
import gi
import subprocess
import glob
import re
import os
import sys
import time

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, Gst, GLib

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
    try:
        for device_path in glob.glob('/dev/video*'):
            device_num = int(re.findall(r'\d+', device_path)[-1])
            if device_num >= 2:  # Skip /dev/video0 and /dev/video1 (GPU modules)
                try:
                    with open(device_path, 'rb') as f:
                        devices.append(device_path)
                except:
                    pass
    except Exception as e:
        print(f"Device detection error: {e}")
    return sorted(devices) if devices else ['/dev/video2']

def get_device_formats(device_path):
    formats = []
    try:
        result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                match = re.search(r"\[(\d+)\]:\s+'([^']+)'\s+\(([^)]+)\)", line)
                if match:
                    code, desc = match.group(2), match.group(3)
                    formats.append((code, f"{code} ({desc})"))
        if not formats:
            raise Exception("No formats detected")
    except Exception as e:
        print(f"Format detection failed for {device_path}: {e}")
        # Fallback to common formats
        formats = [
            ('MJPG', 'MJPG (Motion-JPEG)'),
            ('YUYV', 'YUYV (YUV 4:2:2)'),
            ('H264', 'H264 (H.264 compressed)')
        ]
    return formats

class CompleteCameraWindow(Gtk.Window):
    def __init__(self):
        try:
            super().__init__(type=Gtk.WindowType.TOPLEVEL)
            self.set_title("USB Camera Touch Viewer")
            self.connect("destroy", Gtk.main_quit)

            print("Initializing camera application...")

            # Initialize variables
            self.video_devices = get_video_devices()
            self.device = self.video_devices[0]
            self.available_formats = get_device_formats(self.device)
            self.current_format = self.available_formats[0][0]
            self.width, self.height, self.fps = 640, 480, 30
            self.pipeline = None
            self.is_running = False

            self.res_options = [
                (320, 240), (640, 480), (800, 600), (1280, 720),
                (1280, 800), (1366, 768), (1600, 900), (1920, 1080)
            ]

            print(f"Found devices: {self.video_devices}")
            print(f"Using device: {self.device}")
            print(f"Available formats: {[f[0] for f in self.available_formats]}")

            self.setup_ui()
            print("UI setup complete")

        except Exception as e:
            print(f"Init error: {e}")
            sys.exit(1)

    def setup_ui(self):
        try:
            # Main container
            vbox = Gtk.VBox(spacing=8)
            vbox.set_property("margin", 12)
            self.add(vbox)

            # Status bar
            self.status_label = Gtk.Label(label="Camera application ready")
            vbox.pack_start(self.status_label, False, False, 0)

            # Video area
            self.video_area = Gtk.DrawingArea()
            self.video_area.set_size_request(800, 600)
            vbox.pack_start(self.video_area, True, True, 0)

            # Control panel
            controls_frame = Gtk.Frame(label="Camera Controls")
            controls_frame.set_property("margin", 4)
            vbox.pack_start(controls_frame, False, False, 0)

            controls_grid = Gtk.Grid()
            controls_grid.set_property("margin", 8)
            controls_grid.set_row_spacing(8)
            controls_grid.set_column_spacing(8)
            controls_frame.add(controls_grid)

            row = 0

            # Device selector
            controls_grid.attach(Gtk.Label(label="Device:"), 0, row, 1, 1)
            self.device_combo = Gtk.ComboBoxText()
            for device in self.video_devices:
                self.device_combo.append_text(device)
            self.device_combo.set_active(0)
            self.device_combo.connect("changed", self.on_device_changed)
            controls_grid.attach(self.device_combo, 1, row, 1, 1)

            # Format selector
            controls_grid.attach(Gtk.Label(label="Format:"), 2, row, 1, 1)
            self.format_combo = Gtk.ComboBoxText()
            for code, desc in self.available_formats:
                self.format_combo.append_text(desc)
            self.format_combo.set_active(0)
            self.format_combo.connect("changed", self.on_format_changed)
            controls_grid.attach(self.format_combo, 3, row, 1, 1)

            row += 1

            # Resolution selector
            controls_grid.attach(Gtk.Label(label="Resolution:"), 0, row, 1, 1)
            self.res_combo = Gtk.ComboBoxText()
            for w, h in self.res_options:
                self.res_combo.append_text(f"{w}x{h}")
            self.res_combo.set_active(1)  # 640x480
            self.res_combo.connect("changed", self.on_resolution_changed)
            controls_grid.attach(self.res_combo, 1, row, 1, 1)

            # FPS control
            controls_grid.attach(Gtk.Label(label="FPS:"), 2, row, 1, 1)
            self.fps_scale = Gtk.HScale()
            self.fps_scale.set_range(0, 60)
            self.fps_scale.set_value(30)
            self.fps_scale.set_digits(0)
            self.fps_scale.set_size_request(200, -1)
            self.fps_scale.connect("value-changed", self.on_fps_changed)
            controls_grid.attach(self.fps_scale, 3, row, 2, 1)

            row += 1

            # Control buttons
            button_box = Gtk.HBox(spacing=8)
            controls_grid.attach(button_box, 0, row, 5, 1)

            self.start_btn = Gtk.Button(label="Start Camera")
            self.start_btn.set_size_request(120, 40)
            self.start_btn.connect("clicked", self.on_start_stop)
            button_box.pack_start(self.start_btn, False, False, 0)

            self.apply_btn = Gtk.Button(label="Apply Settings")
            self.apply_btn.set_size_request(120, 40)
            self.apply_btn.connect("clicked", self.on_apply)
            button_box.pack_start(self.apply_btn, False, False, 0)

            self.pause_btn = Gtk.Button(label="Pause")
            self.pause_btn.set_size_request(80, 40)
            self.pause_btn.set_sensitive(False)
            self.pause_btn.connect("clicked", self.on_pause)
            button_box.pack_start(self.pause_btn, False, False, 0)

            # Spacer
            button_box.pack_start(Gtk.Label(), True, True, 0)

            # System monitor
            self.usage_label = Gtk.Label(label="CPU: 0% | RAM: 0%")
            button_box.pack_start(self.usage_label, False, False, 0)

            self.exit_btn = Gtk.Button(label="Exit")
            self.exit_btn.set_size_request(80, 40)
            self.exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
            button_box.pack_start(self.exit_btn, False, False, 0)

            self.show_all()
            self.fullscreen()

            # Initialize GStreamer after window is shown
            GLib.timeout_add(500, self.init_gstreamer)

            # Start system monitoring
            GLib.timeout_add(1000, self.update_usage)

        except Exception as e:
            print(f"UI setup error: {e}")
            sys.exit(1)

    def init_gstreamer(self):
        try:
            Gst.init(None)
            self.status_label.set_text("GStreamer initialized. Ready to start camera.")
            print("GStreamer initialized successfully")
        except Exception as e:
            print(f"GStreamer init error: {e}")
            self.status_label.set_text(f"GStreamer error: {e}")
        return False

    def on_device_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0:
            self.device = self.video_devices[idx]
            self.update_formats()
            print(f"Device changed to: {self.device}")

    def update_formats(self):
        self.available_formats = get_device_formats(self.device)
        self.format_combo.remove_all()
        for code, desc in self.available_formats:
            self.format_combo.append_text(desc)
        self.format_combo.set_active(0)
        self.current_format = self.available_formats[0][0]
        print(f"Updated formats for {self.device}: {[f[0] for f in self.available_formats]}")

    def on_format_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0 and idx < len(self.available_formats):
            self.current_format = self.available_formats[idx][0]
            print(f"Format changed to: {self.current_format}")

    def on_resolution_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0:
            self.width, self.height = self.res_options[idx]
            print(f"Resolution changed to: {self.width}x{self.height}")

    def on_fps_changed(self, scale):
        self.fps = int(scale.get_value())
        print(f"FPS changed to: {self.fps}")

    def on_start_stop(self, btn):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def on_apply(self, btn):
        if self.is_running:
            self.stop_camera()
            self.start_camera()

    def on_pause(self, btn):
        if not self.pipeline:
            return

        if btn.get_label() == "Pause":
            self.pipeline.set_state(Gst.State.PAUSED)
            btn.set_label("Resume")
            self.status_label.set_text("Camera paused")
        else:
            self.pipeline.set_state(Gst.State.PLAYING)
            btn.set_label("Pause")
            self.status_label.set_text("Camera running")

    def start_camera(self):
        try:
            if self.pipeline:
                self.stop_camera()

            # Build pipeline based on format and settings
            if self.current_format == 'MJPG':
                if self.fps > 0:
                    caps = f"image/jpeg,width={self.width},height={self.height},framerate={self.fps}/1"
                else:
                    caps = f"image/jpeg,width={self.width},height={self.height}"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! jpegdec ! videoconvert ! waylandsink"
            elif self.current_format == 'H264':
                if self.fps > 0:
                    caps = f"video/x-h264,width={self.width},height={self.height},framerate={self.fps}/1"
                else:
                    caps = f"video/x-h264,width={self.width},height={self.height}"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! h264parse ! avdec_h264 ! videoconvert ! waylandsink"
            else:
                # Raw formats (YUYV, etc.)
                format_map = {'YUYV': 'YUY2', 'YUV420': 'I420', 'UYVY': 'UYVY'}
                gst_format = format_map.get(self.current_format, 'YUY2')
                if self.fps > 0:
                    caps = f"video/x-raw,format={gst_format},width={self.width},height={self.height},framerate={self.fps}/1"
                else:
                    caps = f"video/x-raw,format={gst_format},width={self.width},height={self.height}"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! videoconvert ! waylandsink"

            print(f"Starting pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)

            if self.fps == 0:
                self.pipeline.set_state(Gst.State.PAUSED)
                self.status_label.set_text("Camera paused (0 FPS)")
                self.pause_btn.set_label("Resume")
            else:
                self.pipeline.set_state(Gst.State.PLAYING)
                self.status_label.set_text("Camera running")
                self.pause_btn.set_label("Pause")

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.pause_btn.set_sensitive(True)
            print("Camera started successfully")

        except Exception as e:
            print(f"Camera start error: {e}")
            self.status_label.set_text(f"Camera error: {e}")
            # Try fallback pipeline
            try:
                simple_pipeline = f"v4l2src device={self.device} ! videoconvert ! waylandsink"
                self.pipeline = Gst.parse_launch(simple_pipeline)
                self.pipeline.set_state(Gst.State.PLAYING)
                self.is_running = True
                self.start_btn.set_label("Stop Camera")
                self.pause_btn.set_sensitive(True)
                self.status_label.set_text("Camera running (fallback mode)")
                print(f"Fallback pipeline started: {simple_pipeline}")
            except Exception as e2:
                print(f"Fallback failed: {e2}")
                self.status_label.set_text(f"Camera failed: {e2}")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.pause_btn.set_sensitive(False)
        self.pause_btn.set_label("Pause")
        self.status_label.set_text("Camera stopped")
        print("Camera stopped")

    def update_usage(self):
        cpu = read_cpu_percent()
        mem = read_mem_percent()
        self.usage_label.set_text(f"CPU: {cpu:.0f}% | RAM: {mem:.0f}%")
        return True

if __name__ == "__main__":
    try:
        print("Starting complete camera application...")
        app = CompleteCameraWindow()
        print("Entering main loop...")
        Gtk.main()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)