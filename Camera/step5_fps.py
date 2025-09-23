#!/usr/bin/env python3
# Step 5: Camera with FPS control

import gi
import glob
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst

class CameraWithFPS(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 5: Camera with FPS Control")
        self.set_default_size(800, 600)
        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None
        self.is_running = False

        # Find video devices
        self.video_devices = self.get_video_devices()
        self.current_device = self.video_devices[0] if self.video_devices else "/dev/video2"

        # Format and resolution options
        self.formats = ['MJPG', 'YUYV']
        self.current_format = 'MJPG'

        self.resolutions = [(640, 480), (800, 600), (1280, 720), (1920, 1080)]
        self.current_resolution = (640, 480)

        # FPS options
        self.fps_options = [15, 30, 60]
        self.current_fps = 30

        # Create UI
        vbox = Gtk.VBox(spacing=10)
        self.add(vbox)

        # Status label
        self.status_label = Gtk.Label(label="Camera Ready")
        vbox.pack_start(self.status_label, False, False, 0)

        # Controls row 1: Device and Format
        hbox1 = Gtk.HBox(spacing=10)
        vbox.pack_start(hbox1, False, False, 0)

        device_label = Gtk.Label(label="Device:")
        hbox1.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.current_device)
        self.device_btn.connect("clicked", self.cycle_device)
        hbox1.pack_start(self.device_btn, False, False, 0)

        format_label = Gtk.Label(label="Format:")
        hbox1.pack_start(format_label, False, False, 0)

        self.format_btn = Gtk.Button(label=self.current_format)
        self.format_btn.connect("clicked", self.cycle_format)
        hbox1.pack_start(self.format_btn, False, False, 0)

        # Controls row 2: Resolution and FPS
        hbox2 = Gtk.HBox(spacing=10)
        vbox.pack_start(hbox2, False, False, 0)

        res_label = Gtk.Label(label="Resolution:")
        hbox2.pack_start(res_label, False, False, 0)

        self.res_btn = Gtk.Button(label="640x480")
        self.res_btn.connect("clicked", self.cycle_resolution)
        hbox2.pack_start(self.res_btn, False, False, 0)

        fps_label = Gtk.Label(label="FPS:")
        hbox2.pack_start(fps_label, False, False, 0)

        self.fps_btn = Gtk.Button(label="30")
        self.fps_btn.connect("clicked", self.cycle_fps)
        hbox2.pack_start(self.fps_btn, False, False, 0)

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

    def cycle_format(self, btn):
        try:
            current_idx = self.formats.index(self.current_format)
            next_idx = (current_idx + 1) % len(self.formats)
            self.current_format = self.formats[next_idx]
            btn.set_label(self.current_format)
        except Exception as e:
            print(f"Format cycle error: {e}")

    def cycle_resolution(self, btn):
        try:
            current_idx = self.resolutions.index(self.current_resolution)
            next_idx = (current_idx + 1) % len(self.resolutions)
            self.current_resolution = self.resolutions[next_idx]
            w, h = self.current_resolution
            btn.set_label(f"{w}x{h}")
        except Exception as e:
            print(f"Resolution cycle error: {e}")

    def cycle_fps(self, btn):
        try:
            current_idx = self.fps_options.index(self.current_fps)
            next_idx = (current_idx + 1) % len(self.fps_options)
            self.current_fps = self.fps_options[next_idx]
            btn.set_label(str(self.current_fps))
        except Exception as e:
            print(f"FPS cycle error: {e}")

    def on_start_stop(self, btn):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        try:
            w, h = self.current_resolution

            if self.current_format == 'MJPG':
                caps = f"image/jpeg,width={w},height={h},framerate={self.current_fps}/1"
                pipeline_str = f"v4l2src device={self.current_device} ! {caps} ! jpegdec ! videoconvert ! waylandsink"
            else:  # YUYV
                caps = f"video/x-raw,format=YUY2,width={w},height={h},framerate={self.current_fps}/1"
                pipeline_str = f"v4l2src device={self.current_device} ! {caps} ! videoconvert ! waylandsink"

            print(f"Pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.status_label.set_text(f"Running: {self.current_device} {self.current_format} {w}x{h}@{self.current_fps}fps")

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.status_label.set_text(f"Error: {e}")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_text("Camera Stopped")

if __name__ == "__main__":
    app = CameraWithFPS()
    Gtk.main()