#!/usr/bin/env python3
# safe_camera.py - Safe camera app with error handling
import gi
import subprocess
import glob
import re
import os
import sys

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, Gst, GLib

Gdk.set_allowed_backends("wayland")

def get_video_devices():
    devices = []
    try:
        for device_path in glob.glob('/dev/video*'):
            device_num = int(re.findall(r'\d+', device_path)[-1])
            if device_num >= 2:
                try:
                    with open(device_path, 'rb') as f:
                        devices.append(device_path)
                except:
                    pass
    except Exception as e:
        print(f"Device detection error: {e}")
    return sorted(devices) if devices else ['/dev/video2']

def get_device_formats(device_path):
    # Return safe defaults without subprocess for now
    return [('MJPG', 'MJPG (Motion-JPEG)'), ('YUYV', 'YUYV (YUV 4:2:2)')]

class SafeCameraWindow(Gtk.Window):
    def __init__(self):
        try:
            super().__init__(type=Gtk.WindowType.TOPLEVEL)
            self.set_title("Safe Camera")
            self.connect("destroy", Gtk.main_quit)

            print("Window created")

            # Safe initialization
            self.video_devices = get_video_devices()
            self.device = self.video_devices[0]
            self.current_format = 'MJPG'
            self.width, self.height, self.fps = 640, 480, 30
            self.pipeline = None

            print(f"Using device: {self.device}")

            self.setup_ui()
            print("UI setup complete")

        except Exception as e:
            print(f"Init error: {e}")
            sys.exit(1)

    def setup_ui(self):
        try:
            # Simple layout
            vbox = Gtk.VBox(spacing=8)
            self.add(vbox)

            # Status label
            self.status_label = Gtk.Label(label="Camera app starting...")
            vbox.pack_start(self.status_label, False, False, 0)

            # Video placeholder
            self.video_area = Gtk.DrawingArea()
            self.video_area.set_size_request(640, 480)
            vbox.pack_start(self.video_area, True, True, 0)

            # Simple controls
            controls = Gtk.HBox(spacing=8)
            vbox.pack_start(controls, False, False, 0)

            self.start_btn = Gtk.Button(label="Start Camera")
            self.start_btn.connect("clicked", self.start_camera)
            controls.pack_start(self.start_btn, False, False, 0)

            exit_btn = Gtk.Button(label="Exit")
            exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
            controls.pack_start(exit_btn, False, False, 0)

            self.show_all()
            print("Window shown")

            # Initialize GStreamer after window is shown
            GLib.timeout_add(500, self.init_gstreamer)

        except Exception as e:
            print(f"UI setup error: {e}")
            sys.exit(1)

    def init_gstreamer(self):
        try:
            Gst.init(None)
            self.status_label.set_text("GStreamer initialized. Ready to start camera.")
            print("GStreamer initialized")
        except Exception as e:
            print(f"GStreamer init error: {e}")
            self.status_label.set_text(f"GStreamer error: {e}")
        return False

    def start_camera(self, btn):
        try:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                btn.set_label("Start Camera")
                self.status_label.set_text("Camera stopped")
                return

            # Simple working pipeline
            pipeline_str = f"v4l2src device={self.device} ! videoconvert ! waylandsink"
            print(f"Creating pipeline: {pipeline_str}")

            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            btn.set_label("Stop Camera")
            self.status_label.set_text("Camera running")
            print("Camera started successfully")

        except Exception as e:
            print(f"Camera start error: {e}")
            self.status_label.set_text(f"Camera error: {e}")

if __name__ == "__main__":
    try:
        print("Starting camera app...")
        app = SafeCameraWindow()
        print("Entering main loop...")
        Gtk.main()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)