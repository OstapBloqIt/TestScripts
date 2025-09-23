#!/usr/bin/env python3
# stable_camera.py - Remove problematic fullscreen timing
import gi
import subprocess
import glob
import re
import os
import sys
import time

print("STEP 1: Importing gi")
print("STEP 2: Setting GTK version requirement")
gi.require_version("Gtk", "3.0")
print("STEP 3: Setting Gst version requirement")
gi.require_version("Gst", "1.0")
print("STEP 4: Importing from gi.repository")
from gi.repository import Gtk, Gdk, Gst, GLib

print("STEP 5: Setting Wayland backend")
Gdk.set_allowed_backends("wayland")
print("STEP 6: Backend set successfully")

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
    print("STEP 7: Getting video devices")
    devices = []
    for device_path in glob.glob('/dev/video*'):
        device_num = int(re.findall(r'\d+', device_path)[-1])
        if device_num >= 2:
            try:
                with open(device_path, 'rb') as f:
                    devices.append(device_path)
            except:
                pass
    print(f"STEP 8: Found devices: {devices}")
    return sorted(devices) if devices else ['/dev/video2']

def get_device_formats(device_path):
    print(f"STEP 9: Getting formats for {device_path}")
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
            print(f"STEP 10: Detected formats: {formats}")
            return formats if formats else [('MJPG', 'MJPG (Motion-JPEG)')]
    except Exception as e:
        print(f"STEP 10: Format detection failed: {e}")
        pass
    fallback = [('MJPG', 'MJPG (Motion-JPEG)'), ('YUYV', 'YUYV (YUV 4:2:2)')]
    print(f"STEP 11: Using fallback formats: {fallback}")
    return fallback

class StableCameraWindow(Gtk.Window):
    def __init__(self):
        print("STEP 12: Creating StableCameraWindow")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        print("STEP 13: Window superclass initialized")

        self.set_title("USB Camera Touch Viewer")
        print("STEP 14: Window title set")

        self.connect("destroy", Gtk.main_quit)
        print("STEP 15: Destroy signal connected")

        # Set large size but NO fullscreen() call
        self.set_default_size(1200, 800)
        print("STEP 16: Default size set")

        self.maximize()  # Use maximize instead of fullscreen
        print("STEP 17: Window maximized")

        print("STEP 18: Window created successfully")

        # Initialize variables
        print("STEP 19: Getting video devices")
        self.video_devices = get_video_devices()

        print("STEP 20: Setting default device")
        self.device = self.video_devices[0]

        print("STEP 21: Getting device formats")
        self.available_formats = get_device_formats(self.device)

        print("STEP 22: Setting current format")
        self.current_format = self.available_formats[0][0]

        print("STEP 23: Setting default parameters")
        self.width, self.height, self.fps = 640, 480, 30
        self.pipeline = None
        self.is_running = False

        print("STEP 24: Setting resolution options")
        self.res_options = [(320, 240), (640, 480), (800, 600), (1280, 720), (1920, 1080)]

        print(f"STEP 25: Using device: {self.device}")
        print(f"STEP 26: Available formats: {[f[0] for f in self.available_formats]}")

        print("STEP 27: Starting UI setup")
        self.setup_ui()
        print("STEP 28: UI setup complete")

    def setup_ui(self):
        print("STEP 29: Creating main VBox")
        vbox = Gtk.VBox(spacing=8)
        print("STEP 30: Setting VBox margin")
        vbox.set_property("margin", 12)
        print("STEP 31: Adding VBox to window")
        self.add(vbox)

        print("STEP 32: Creating status label")
        # Status label
        self.status_label = Gtk.Label(label="Camera app ready - Press F11 for fullscreen")
        print("STEP 33: Packing status label")
        vbox.pack_start(self.status_label, False, False, 0)

        print("STEP 34: Creating video area")
        # Video area
        self.video_area = Gtk.DrawingArea()
        print("STEP 35: Setting video area size")
        self.video_area.set_size_request(800, 600)
        print("STEP 36: Packing video area")
        vbox.pack_start(self.video_area, True, True, 0)

        # Controls in a single row
        controls = Gtk.HBox(spacing=8)
        vbox.pack_start(controls, False, False, 0)

        # Device
        controls.pack_start(Gtk.Label(label="Device:"), False, False, 0)
        self.device_combo = Gtk.ComboBoxText()
        for device in self.video_devices:
            self.device_combo.append_text(device)
        self.device_combo.set_active(0)
        self.device_combo.connect("changed", self.on_device_changed)
        controls.pack_start(self.device_combo, False, False, 0)

        # Format
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
        self.res_combo.set_active(1)
        self.res_combo.connect("changed", self.on_resolution_changed)
        controls.pack_start(self.res_combo, False, False, 0)

        # FPS
        controls.pack_start(Gtk.Label(label="FPS:"), False, False, 0)
        self.fps_scale = Gtk.HScale()
        self.fps_scale.set_range(0, 60)
        self.fps_scale.set_value(30)
        self.fps_scale.set_digits(0)
        self.fps_scale.set_size_request(150, -1)
        self.fps_scale.connect("value-changed", self.on_fps_changed)
        controls.pack_start(self.fps_scale, False, False, 0)

        # Buttons
        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.set_size_request(100, 40)
        self.start_btn.connect("clicked", self.on_start_stop)
        controls.pack_start(self.start_btn, False, False, 0)

        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.set_size_request(80, 40)
        self.apply_btn.connect("clicked", self.on_apply)
        controls.pack_start(self.apply_btn, False, False, 0)

        # Fullscreen toggle button instead of automatic
        self.fs_btn = Gtk.Button(label="Fullscreen")
        self.fs_btn.set_size_request(100, 40)
        self.fs_btn.connect("clicked", self.toggle_fullscreen)
        controls.pack_start(self.fs_btn, False, False, 0)

        # System monitor
        self.usage_label = Gtk.Label(label="CPU 0% | RAM 0%")
        controls.pack_start(self.usage_label, False, False, 0)

        # Exit
        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(80, 40)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        controls.pack_start(exit_btn, False, False, 0)

        print("STEP 50: Calling show_all()")
        self.show_all()
        print("STEP 51: Window shown successfully")

        print("STEP 52: Setting up GStreamer timeout")
        # Initialize GStreamer after window is shown
        GLib.timeout_add(500, self.init_gstreamer)
        print("STEP 53: Setting up usage monitoring timeout")
        GLib.timeout_add(1000, self.update_usage)
        print("STEP 54: All timeouts set")

    def toggle_fullscreen(self, btn):
        """Manual fullscreen toggle"""
        try:
            if btn.get_label() == "Fullscreen":
                self.fullscreen()
                btn.set_label("Windowed")
            else:
                self.unfullscreen()
                btn.set_label("Fullscreen")
        except Exception as e:
            print(f"Fullscreen toggle error: {e}")

    def init_gstreamer(self):
        try:
            Gst.init(None)
            self.status_label.set_text("GStreamer ready. Click Start Camera to begin.")
            print("GStreamer initialized")
        except Exception as e:
            print(f"GStreamer init error: {e}")
            self.status_label.set_text(f"GStreamer error: {e}")
        return False

    def on_device_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0:
            self.device = self.video_devices[idx]
            self.update_formats()

    def update_formats(self):
        self.available_formats = get_device_formats(self.device)
        self.format_combo.remove_all()
        for code, desc in self.available_formats:
            self.format_combo.append_text(desc)
        self.format_combo.set_active(0)
        self.current_format = self.available_formats[0][0]

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

            # Simple working pipeline
            if self.current_format == 'MJPG' and self.fps > 0:
                caps = f"image/jpeg,width={self.width},height={self.height},framerate={self.fps}/1"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! jpegdec ! videoconvert ! waylandsink"
            elif self.fps > 0:
                caps = f"video/x-raw,format=YUY2,width={self.width},height={self.height},framerate={self.fps}/1"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! videoconvert ! waylandsink"
            else:
                # 0 FPS = basic pipeline
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
                # Ultra-simple fallback
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
        cpu = read_cpu_percent()
        mem = read_mem_percent()
        self.usage_label.set_text(f"CPU {cpu:.0f}% | RAM {mem:.0f}%")
        return True

if __name__ == "__main__":
    print("MAIN: Starting stable camera app...")
    print("MAIN: Creating StableCameraWindow instance")
    app = StableCameraWindow()
    print("MAIN: StableCameraWindow created successfully")
    print("MAIN: About to enter Gtk.main() loop...")
    try:
        Gtk.main()
        print("MAIN: Gtk.main() completed normally")
    except Exception as e:
        print(f"MAIN: Exception in Gtk.main(): {e}")
        import traceback
        traceback.print_exc()