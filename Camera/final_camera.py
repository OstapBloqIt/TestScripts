#!/usr/bin/env python3
# final_camera.py - Working camera app with simplified UI
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
    for device_path in glob.glob('/dev/video*'):
        device_num = int(re.findall(r'\d+', device_path)[-1])
        if device_num >= 2:
            try:
                with open(device_path, 'rb') as f:
                    devices.append(device_path)
            except:
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

class FinalCameraWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("USB Camera Touch Viewer")
        self.connect("destroy", Gtk.main_quit)

        self.set_default_size(1200, 800)
        self.maximize()

        # Initialize variables
        self.video_devices = get_video_devices()
        self.device = self.video_devices[0]
        self.available_formats = get_device_formats(self.device)
        self.current_format = self.available_formats[0][0]
        self.width, self.height, self.fps = 640, 480, 30
        self.pipeline = None
        self.is_running = False

        # Simplified resolution list
        self.res_options = [(640, 480), (800, 600), (1280, 720), (1920, 1080)]

        print(f"Using device: {self.device}")
        print(f"Available formats: {[f[0] for f in self.available_formats]}")

        self.setup_simple_ui()

    def setup_simple_ui(self):
        # SIMPLIFIED layout - avoid complex nested widgets
        main_box = Gtk.VBox(spacing=10)
        main_box.set_property("margin", 10)
        self.add(main_box)

        # Status area
        self.status_label = Gtk.Label(label="Camera Ready")
        main_box.pack_start(self.status_label, False, False, 0)

        # Video area - simple DrawingArea
        self.video_area = Gtk.DrawingArea()
        self.video_area.set_size_request(800, 600)
        main_box.pack_start(self.video_area, True, True, 0)

        # SIMPLIFIED controls - use MINIMAL widgets
        controls1 = Gtk.HBox(spacing=10)
        main_box.pack_start(controls1, False, False, 0)

        # Device selection - simplified
        device_label = Gtk.Label(label="Device:")
        controls1.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.device)
        self.device_btn.connect("clicked", self.cycle_device)
        controls1.pack_start(self.device_btn, False, False, 0)

        # Format selection - simplified
        format_label = Gtk.Label(label="Format:")
        controls1.pack_start(format_label, False, False, 0)

        self.format_btn = Gtk.Button(label=self.current_format)
        self.format_btn.connect("clicked", self.cycle_format)
        controls1.pack_start(self.format_btn, False, False, 0)

        # Resolution selection - simplified
        res_label = Gtk.Label(label="Resolution:")
        controls1.pack_start(res_label, False, False, 0)

        self.res_btn = Gtk.Button(label="640x480")
        self.res_btn.connect("clicked", self.cycle_resolution)
        controls1.pack_start(self.res_btn, False, False, 0)

        # Second row of controls
        controls2 = Gtk.HBox(spacing=10)
        main_box.pack_start(controls2, False, False, 0)

        # FPS control - simplified (no HScale)
        fps_label = Gtk.Label(label="FPS:")
        controls2.pack_start(fps_label, False, False, 0)

        self.fps_btn = Gtk.Button(label="30")
        self.fps_btn.connect("clicked", self.cycle_fps)
        controls2.pack_start(self.fps_btn, False, False, 0)

        # Control buttons
        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.set_size_request(120, 40)
        self.start_btn.connect("clicked", self.on_start_stop)
        controls2.pack_start(self.start_btn, False, False, 0)

        self.apply_btn = Gtk.Button(label="Apply Settings")
        self.apply_btn.set_size_request(120, 40)
        self.apply_btn.connect("clicked", self.on_apply)
        controls2.pack_start(self.apply_btn, False, False, 0)

        # Fullscreen button
        self.fs_btn = Gtk.Button(label="Fullscreen")
        self.fs_btn.set_size_request(100, 40)
        self.fs_btn.connect("clicked", self.toggle_fullscreen)
        controls2.pack_start(self.fs_btn, False, False, 0)

        # System monitor and exit
        self.usage_label = Gtk.Label(label="CPU 0% | RAM 0%")
        controls2.pack_start(self.usage_label, True, True, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(80, 40)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        controls2.pack_start(exit_btn, False, False, 0)

        self.show_all()

        # SINGLE timeout instead of multiple
        GLib.timeout_add(2000, self.delayed_init)

    def delayed_init(self):
        """Single delayed initialization"""
        try:
            Gst.init(None)
            self.status_label.set_text("GStreamer ready. Click Start Camera.")
            # Start usage monitoring
            GLib.timeout_add(2000, self.update_usage)  # Slower update rate
        except Exception as e:
            self.status_label.set_text(f"GStreamer error: {e}")
        return False

    def cycle_device(self, btn):
        """Cycle through available devices"""
        try:
            current_idx = self.video_devices.index(self.device)
            next_idx = (current_idx + 1) % len(self.video_devices)
            self.device = self.video_devices[next_idx]
            btn.set_label(self.device)
            # Update formats for new device
            self.available_formats = get_device_formats(self.device)
            self.current_format = self.available_formats[0][0]
            self.format_btn.set_label(self.current_format)
        except Exception as e:
            print(f"Device cycle error: {e}")

    def cycle_format(self, btn):
        """Cycle through available formats"""
        try:
            current_idx = next((i for i, (code, _) in enumerate(self.available_formats) if code == self.current_format), 0)
            next_idx = (current_idx + 1) % len(self.available_formats)
            self.current_format = self.available_formats[next_idx][0]
            btn.set_label(self.current_format)
        except Exception as e:
            print(f"Format cycle error: {e}")

    def cycle_resolution(self, btn):
        """Cycle through resolutions"""
        try:
            current_idx = next((i for i, (w, h) in enumerate(self.res_options) if w == self.width and h == self.height), 0)
            next_idx = (current_idx + 1) % len(self.res_options)
            self.width, self.height = self.res_options[next_idx]
            btn.set_label(f"{self.width}x{self.height}")
        except Exception as e:
            print(f"Resolution cycle error: {e}")

    def cycle_fps(self, btn):
        """Cycle through common FPS values"""
        fps_options = [0, 15, 30, 60]
        try:
            current_idx = fps_options.index(self.fps) if self.fps in fps_options else 2
            next_idx = (current_idx + 1) % len(fps_options)
            self.fps = fps_options[next_idx]
            btn.set_label(str(self.fps))
        except Exception as e:
            print(f"FPS cycle error: {e}")

    def toggle_fullscreen(self, btn):
        """Toggle fullscreen mode"""
        try:
            if btn.get_label() == "Fullscreen":
                self.fullscreen()
                btn.set_label("Windowed")
            else:
                self.unfullscreen()
                btn.set_label("Fullscreen")
        except Exception as e:
            print(f"Fullscreen toggle error: {e}")

    def on_start_stop(self, btn):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def on_apply(self, btn):
        if self.is_running:
            self.stop_camera()
            self.start_camera()

    def start_camera(self):
        try:
            if self.pipeline:
                self.stop_camera()

            # Build simple pipeline
            if self.current_format == 'MJPG' and self.fps > 0:
                caps = f"image/jpeg,width={self.width},height={self.height},framerate={self.fps}/1"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! jpegdec ! videoconvert ! waylandsink"
            elif self.fps > 0:
                caps = f"video/x-raw,format=YUY2,width={self.width},height={self.height},framerate={self.fps}/1"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! videoconvert ! waylandsink"
            else:
                pipeline_str = f"v4l2src device={self.device} ! videoconvert ! waylandsink"

            print(f"Pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)

            if self.fps == 0:
                self.pipeline.set_state(Gst.State.PAUSED)
                self.status_label.set_text("Camera paused (0 FPS)")
            else:
                self.pipeline.set_state(Gst.State.PLAYING)
                self.status_label.set_text(f"Camera: {self.current_format} {self.width}x{self.height}@{self.fps}fps")

            self.is_running = True
            self.start_btn.set_label("Stop Camera")

        except Exception as e:
            print(f"Pipeline error: {e}")
            try:
                fallback = f"v4l2src device={self.device} ! videoconvert ! waylandsink"
                self.pipeline = Gst.parse_launch(fallback)
                self.pipeline.set_state(Gst.State.PLAYING)
                self.is_running = True
                self.start_btn.set_label("Stop Camera")
                self.status_label.set_text("Camera running (basic mode)")
                print(f"Fallback: {fallback}")
            except Exception as e2:
                print(f"Complete failure: {e2}")
                self.status_label.set_text(f"Failed: {e2}")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_text("Camera stopped")

    def update_usage(self):
        try:
            cpu = read_cpu_percent()
            mem = read_mem_percent()
            self.usage_label.set_text(f"CPU {cpu:.0f}% | RAM {mem:.0f}%")
        except:
            pass
        return True

if __name__ == "__main__":
    print("Starting final camera app...")
    app = FinalCameraWindow()
    print("Entering main loop...")
    Gtk.main()