#!/usr/bin/env python3
# full_camera.py - Complete camera app with all features
import gi
import subprocess
import glob
import re
import os

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, Gst, GLib

Gdk.set_allowed_backends("wayland")

def get_video_devices():
    devices = []
    for device_path in glob.glob('/dev/video*'):
        device_num = int(re.findall(r'\d+', device_path)[-1])
        if device_num >= 2:  # Skip /dev/video0 and /dev/video1
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

class FullCameraWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("USB Camera Touch Viewer")
        self.connect("destroy", Gtk.main_quit)

        # Initialize variables
        self.video_devices = get_video_devices()
        self.device = self.video_devices[0]
        self.available_formats = get_device_formats(self.device)
        self.current_format = self.available_formats[0][0]
        self.width, self.height, self.fps = 640, 480, 30
        self.pipeline = None

        self.res_options = [(320, 240), (640, 480), (800, 600), (1280, 720), (1920, 1080)]

        self.setup_ui()
        self.show_all()
        self.fullscreen()

        # Initialize GStreamer AFTER UI is shown
        Gst.init(None)

        # Auto-start camera
        GLib.timeout_add(1000, self.start_camera)  # Start after 1 second

    def setup_ui(self):
        vbox = Gtk.VBox(spacing=8)
        vbox.set_property("margin", 12)
        self.add(vbox)

        # Video area
        self.video_area = Gtk.Box()
        self.video_area.set_size_request(800, 600)
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
        controls.pack_start(Gtk.Label(label="Resolution:"), False, False, 0)
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
        self.fps_scale.set_size_request(150, -1)
        self.fps_scale.connect("value-changed", self.on_fps_changed)
        controls.pack_start(self.fps_scale, False, False, 0)

        # Buttons
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.connect("clicked", self.on_apply)
        controls.pack_start(self.apply_btn, False, False, 0)

        self.exit_btn = Gtk.Button(label="Exit")
        self.exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        controls.pack_start(self.exit_btn, False, False, 0)

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

    def on_apply(self, btn):
        self.start_camera()

    def start_camera(self, *args):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        try:
            # Build pipeline based on format
            if self.current_format == 'MJPG':
                caps = f"image/jpeg,width={self.width},height={self.height},framerate={self.fps}/1"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! jpegdec ! videoconvert ! waylandsink"
            else:
                # Raw formats
                format_map = {'YUYV': 'YUY2', 'YUV420': 'I420', 'UYVY': 'UYVY'}
                gst_format = format_map.get(self.current_format, 'YUY2')
                caps = f"video/x-raw,format={gst_format},width={self.width},height={self.height},framerate={self.fps}/1"
                pipeline_str = f"v4l2src device={self.device} ! {caps} ! videoconvert ! waylandsink"

            print(f"Pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

        except Exception as e:
            print(f"Pipeline error: {e}")
            # Fallback to simple pipeline
            try:
                simple_pipeline = f"v4l2src device={self.device} ! videoconvert ! waylandsink"
                self.pipeline = Gst.parse_launch(simple_pipeline)
                self.pipeline.set_state(Gst.State.PLAYING)
                print(f"Fallback pipeline: {simple_pipeline}")
            except Exception as e2:
                print(f"Fallback failed: {e2}")

        return False  # Don't repeat timeout
