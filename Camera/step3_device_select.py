#!/usr/bin/env python3
# Step 3: Camera with device selection (fixed warnings)

import gi
import glob
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst

class CameraWithDeviceSelect(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 3: Camera with Device Selection")
        self.set_default_size(800, 600)
        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None
        self.is_running = False

        # Find video devices
        self.video_devices = self.get_video_devices()
        self.current_device = self.video_devices[0] if self.video_devices else "/dev/video2"

        # Create UI
        vbox = Gtk.VBox(spacing=10)
        self.add(vbox)

        # Status label
        self.status_label = Gtk.Label(label="Camera Ready")
        vbox.pack_start(self.status_label, False, False, 0)

        # Device selection
        hbox = Gtk.HBox(spacing=10)
        vbox.pack_start(hbox, False, False, 0)

        device_label = Gtk.Label(label="Device:")
        hbox.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.current_device)
        self.device_btn.connect("clicked", self.cycle_device)
        hbox.pack_start(self.device_btn, False, False, 0)

        # Start/Stop button
        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.connect("clicked", self.on_start_stop)
        vbox.pack_start(self.start_btn, False, False, 0)

        self.show_all()

    def get_video_devices(self):
        devices = []
        for device_path in glob.glob('/dev/video*'):
            try:
                with open(device_path, 'rb') as f:
                    devices.append(device_path)
            except:
                pass
        return sorted(devices) if devices else ['/dev/video2']

    def cycle_device(self, btn):
        try:
            current_idx = self.video_devices.index(self.current_device)
            next_idx = (current_idx + 1) % len(self.video_devices)
            self.current_device = self.video_devices[next_idx]
            btn.set_label(self.current_device)
        except Exception as e:
            print(f"Device cycle error: {e}")

    def on_start_stop(self, btn):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        try:
            pipeline_str = f"v4l2src device={self.current_device} ! videoconvert ! waylandsink"
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.status_label.set_text(f"Camera Running: {self.current_device}")

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
    app = CameraWithDeviceSelect()
    Gtk.main()