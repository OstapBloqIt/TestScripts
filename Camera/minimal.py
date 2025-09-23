 #!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
Gdk.set_allowed_backends("wayland")

class TestWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Test")
        self.connect("destroy", Gtk.main_quit)
        label = Gtk.Label(label="Test")
        self.add(label)
        self.show_all()

TestWindow()
Gtk.main()
