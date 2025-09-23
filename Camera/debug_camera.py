#!/usr/bin/env python3
# debug_camera.py - Remove suspect elements to find the culprit
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

Gdk.set_allowed_backends("wayland")

class DebugCameraWindow(Gtk.Window):
    def __init__(self):
        print("Creating minimal window...")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Debug Camera")
        self.connect("destroy", Gtk.main_quit)

        # DON'T call maximize() - this might be the issue
        self.set_default_size(800, 600)

        print("Setting up minimal UI...")
        vbox = Gtk.VBox(spacing=8)
        self.add(vbox)

        label = Gtk.Label(label="Debug test - no maximize()")
        vbox.pack_start(label, True, True, 0)

        btn = Gtk.Button(label="Test")
        vbox.pack_start(btn, False, False, 0)

        print("Showing window...")
        self.show_all()
        print("Window shown successfully")

if __name__ == "__main__":
    print("Creating debug window...")
    app = DebugCameraWindow()
    print("Entering main loop...")
    Gtk.main()