#!/usr/bin/env python3
# test_gstreamer.py - Test if GStreamer import is the culprit
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")  # This line might be the issue
from gi.repository import Gtk, Gdk, Gst, GLib  # Adding Gst here might be the issue

Gdk.set_allowed_backends("wayland")

class TestGStreamerWindow(Gtk.Window):
    def __init__(self):
        print("Creating window with GStreamer imports...")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Test GStreamer")
        self.connect("destroy", Gtk.main_quit)

        self.set_default_size(800, 600)

        vbox = Gtk.VBox(spacing=8)
        self.add(vbox)

        label = Gtk.Label(label="Testing GStreamer imports")
        vbox.pack_start(label, True, True, 0)

        btn = Gtk.Button(label="Test")
        vbox.pack_start(btn, False, False, 0)

        print("Showing window...")
        self.show_all()
        print("Window shown successfully")

if __name__ == "__main__":
    print("Testing GStreamer imports...")
    app = TestGStreamerWindow()
    print("Entering main loop...")
    Gtk.main()