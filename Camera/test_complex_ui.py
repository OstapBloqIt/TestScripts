#!/usr/bin/env python3
# test_complex_ui.py - Test if complex UI is the culprit
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, Gst, GLib

Gdk.set_allowed_backends("wayland")

class TestComplexUIWindow(Gtk.Window):
    def __init__(self):
        print("Creating window with complex UI...")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Test Complex UI")
        self.connect("destroy", Gtk.main_quit)

        self.set_default_size(1200, 800)
        self.maximize()

        print("Setting up complex UI...")
        vbox = Gtk.VBox(spacing=8)
        vbox.set_property("margin", 12)
        self.add(vbox)

        # Status label
        self.status_label = Gtk.Label(label="Complex UI test")
        vbox.pack_start(self.status_label, False, False, 0)

        # Video area
        self.video_area = Gtk.DrawingArea()
        self.video_area.set_size_request(800, 600)
        vbox.pack_start(self.video_area, True, True, 0)

        # Multiple controls like the real app
        controls = Gtk.HBox(spacing=8)
        vbox.pack_start(controls, False, False, 0)

        # Multiple dropdowns
        for i, label in enumerate(["Device", "Format", "Resolution"]):
            controls.pack_start(Gtk.Label(label=f"{label}:"), False, False, 0)
            combo = Gtk.ComboBoxText()
            combo.append_text(f"Option {i+1}")
            combo.append_text(f"Option {i+2}")
            combo.set_active(0)
            controls.pack_start(combo, False, False, 0)

        # Scale widget
        controls.pack_start(Gtk.Label(label="FPS:"), False, False, 0)
        fps_scale = Gtk.HScale()
        fps_scale.set_range(0, 60)
        fps_scale.set_value(30)
        fps_scale.set_digits(0)
        fps_scale.set_size_request(150, -1)
        controls.pack_start(fps_scale, False, False, 0)

        # Multiple buttons
        for label in ["Start", "Apply", "Fullscreen", "Exit"]:
            btn = Gtk.Button(label=label)
            btn.set_size_request(80, 40)
            controls.pack_start(btn, False, False, 0)

        # Usage label
        usage_label = Gtk.Label(label="CPU 0% | RAM 0%")
        controls.pack_start(usage_label, False, False, 0)

        print("Adding timeouts...")
        # Multiple timeouts like the real app
        GLib.timeout_add(500, lambda: print("Timeout 1 fired") or True)
        GLib.timeout_add(1000, lambda: print("Timeout 2 fired") or True)

        print("Showing window...")
        self.show_all()
        print("Window shown successfully")

if __name__ == "__main__":
    print("Testing complex UI...")
    app = TestComplexUIWindow()
    print("Entering main loop...")
    Gtk.main()