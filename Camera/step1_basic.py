#!/usr/bin/env python3
# Step 1: Absolute minimum camera display

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst

class BasicCamera(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 1: Basic Camera")
        self.set_default_size(800, 600)
        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)

        # Create simple pipeline
        pipeline_str = "v4l2src device=/dev/video2 ! videoconvert ! waylandsink"
        self.pipeline = Gst.parse_launch(pipeline_str)

        # Start immediately
        self.pipeline.set_state(Gst.State.PLAYING)

        self.show_all()

if __name__ == "__main__":
    app = BasicCamera()
    Gtk.main()