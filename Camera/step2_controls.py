#!/usr/bin/env python3
# Step 2: Basic camera with start/stop controls

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst

class CameraWithControls(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 2: Camera with Controls")
        self.set_default_size(800, 600)
        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None
        self.is_running = False

        # Create UI
        vbox = Gtk.VBox(spacing=10)
        self.add(vbox)

        # Status label
        self.status_label = Gtk.Label("Camera Ready")
        vbox.pack_start(self.status_label, False, False, 0)

        # Start/Stop button
        self.start_btn = Gtk.Button("Start Camera")
        self.start_btn.connect("clicked", self.on_start_stop)
        vbox.pack_start(self.start_btn, False, False, 0)

        self.show_all()

    def on_start_stop(self, btn):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        try:
            pipeline_str = "v4l2src device=/dev/video2 ! videoconvert ! waylandsink"
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.status_label.set_text("Camera Running")

        except Exception as e:
            self.status_label.set_text(f"Error: {e}")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_text("Camera Stopped")

if __name__ == "__main__":
    app = CameraWithControls()
    Gtk.main()