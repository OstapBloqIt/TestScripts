#!/usr/bin/env python3
# test_maximize.py - Test if maximize() is the culprit
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

Gdk.set_allowed_backends("wayland")

class TestMaximizeWindow(Gtk.Window):
    def __init__(self):
        print("Creating window with maximize...")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Test Maximize")
        self.connect("destroy", Gtk.main_quit)

        self.set_default_size(800, 600)

        # THIS is the suspect line from stable_camera.py
        print("About to call maximize()...")
        self.maximize()
        print("maximize() called successfully")

        vbox = Gtk.VBox(spacing=8)
        self.add(vbox)

        label = Gtk.Label(label="Testing maximize() call")
        vbox.pack_start(label, True, True, 0)

        btn = Gtk.Button(label="Test")
        vbox.pack_start(btn, False, False, 0)

        print("Showing window...")
        self.show_all()
        print("Window shown successfully")

if __name__ == "__main__":
    print("Testing maximize() function...")
    app = TestMaximizeWindow()
    print("Entering main loop...")
    Gtk.main()