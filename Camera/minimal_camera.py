#!/usr/bin/env python3
# working_camera.py - Fixed camera app
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, Gst

Gdk.set_allowed_backends("wayland")

def on_resize(self, widget, allocation):
    margin_x = int(allocation.width * 0.10)
    margin_y = int(allocation.height * 0.10)
    self.btn.set_margin_right(margin_x)
    self.btn.set_margin_top(margin_y)

class CameraWindow(Gtk.Window):
    def __init__(self):
    super().__init__(type=Gtk.WindowType.TOPLEVEL)
    self.set_title("Working Camera")
    self.connect("destroy", Gtk.main_quit)

    vbox = Gtk.VBox()
    self.add(vbox)

    # Overlay holds video + button
    overlay = Gtk.Overlay()
    vbox.pack_start(overlay, True, True, 0)

    # Video area
    self.video_area = Gtk.Box()
    self.video_area.set_size_request(640, 480)
    overlay.add(self.video_area)

    # Start Camera button
    self.btn = Gtk.Button(label="Start Camera")
    self.btn.connect("clicked", self.start_camera)
    overlay.add_overlay(self.btn)

    # Position button top-right
    self.btn.set_halign(Gtk.Align.END)
    self.btn.set_valign(Gtk.Align.START)

    # Update margins whenever window resizes → keeps 10% offset
    self.connect("size-allocate", self.on_resize)

    self.show_all()
    self.fullscreen()

    Gst.init(None)
    self.pipeline = None

    def start_camera(self, btn):
        if self.pipeline:
            return

        try:
            # Try waylandsink first (best for Wayland), fallback to autovideosink
            pipeline_str = "v4l2src device=/dev/video2 ! videoconvert ! waylandsink"
            self.pipeline = Gst.parse_launch(pipeline_str)
            print(f"Using: {pipeline_str}")
        except:
            try:
                pipeline_str = "v4l2src device=/dev/video2 ! videoconvert ! autovideosink"
                self.pipeline = Gst.parse_launch(pipeline_str)
                print(f"Fallback to: {pipeline_str}")
            except Exception as e:
                print(f"Pipeline failed: {e}")
                return

        self.pipeline.set_state(Gst.State.PLAYING)
        btn.set_label("Camera Running")

CameraWindow()
Gtk.main()
