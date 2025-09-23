#!/usr/bin/env python3
# Step 6: Camera with fixed layout for rotated 1280x800 display

import gi
import glob
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, Gdk

class CameraWithLayout(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 6: Camera with Fixed Layout")

        # Fixed window positioning and size for 1280x800 rotated display
        # For rotated display: actual screen is 800 wide x 1280 tall
        self.set_default_size(800, 1280)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)  # Prevent resizing to keep layout consistent

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

        self.setup_layout()

    def setup_layout(self):
        # Main vertical box
        main_vbox = Gtk.VBox(spacing=0)
        self.add(main_vbox)

        # TOP AREA (50% height): Controls
        controls_frame = Gtk.Frame()
        controls_frame.set_size_request(800, 640)  # Top half
        controls_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(controls_frame, False, False, 0)

        # Controls container with padding
        controls_vbox = Gtk.VBox(spacing=15)
        controls_vbox.set_property("margin", 20)
        controls_frame.add(controls_vbox)

        # Status label
        self.status_label = Gtk.Label(label="Camera Ready")
        self.status_label.set_markup("<span font='20'><b>Camera Ready</b></span>")
        controls_vbox.pack_start(self.status_label, False, False, 0)

        # Controls row 1: Device and Format
        hbox1 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox1, False, False, 0)

        device_label = Gtk.Label(label="Device:")
        device_label.set_markup("<span font='16'>Device:</span>")
        hbox1.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.current_device)
        self.device_btn.set_size_request(200, 50)
        self.device_btn.connect("clicked", self.cycle_device)
        hbox1.pack_start(self.device_btn, False, False, 0)

        format_label = Gtk.Label(label="Format:")
        format_label.set_markup("<span font='16'>Format:</span>")
        hbox1.pack_start(format_label, False, False, 0)

        self.format_btn = Gtk.Button(label=self.current_format)
        self.format_btn.set_size_request(120, 50)
        self.format_btn.connect("clicked", self.cycle_format)
        hbox1.pack_start(self.format_btn, False, False, 0)

        # Controls row 2: Resolution and FPS
        hbox2 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox2, False, False, 0)

        res_label = Gtk.Label(label="Resolution:")
        res_label.set_markup("<span font='16'>Resolution:</span>")
        hbox2.pack_start(res_label, False, False, 0)

        self.res_btn = Gtk.Button(label="640x480")
        self.res_btn.set_size_request(150, 50)
        self.res_btn.connect("clicked", self.cycle_resolution)
        hbox2.pack_start(self.res_btn, False, False, 0)

        fps_label = Gtk.Label(label="FPS:")
        fps_label.set_markup("<span font='16'>FPS:</span>")
        hbox2.pack_start(fps_label, False, False, 0)

        self.fps_btn = Gtk.Button(label="30")
        self.fps_btn.set_size_request(80, 50)
        self.fps_btn.connect("clicked", self.cycle_fps)
        hbox2.pack_start(self.fps_btn, False, False, 0)

        # Control buttons row
        hbox3 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox3, False, False, 0)

        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.set_size_request(200, 60)
        self.start_btn.connect("clicked", self.on_start_stop)
        hbox3.pack_start(self.start_btn, False, False, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(100, 60)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        hbox3.pack_start(exit_btn, False, False, 0)

        # BOTTOM AREA (50% height): Video display
        video_frame = Gtk.Frame()
        video_frame.set_size_request(800, 640)  # Bottom half
        video_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(video_frame, True, True, 0)

        # Video area - this will be where GStreamer displays video
        self.video_area = Gtk.DrawingArea()
        self.video_area.set_size_request(800, 640)
        self.video_area.set_double_buffered(False)
        video_frame.add(self.video_area)

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

            # Get video area window for embedding
            video_window = self.video_area.get_window()
            if video_window:
                video_window_handle = video_window.get_xid()

                if self.current_format == 'MJPG':
                    caps = f"image/jpeg,width={w},height={h},framerate={self.current_fps}/1"
                    pipeline_str = f"v4l2src device={self.current_device} ! {caps} ! jpegdec ! videoconvert ! xvimagesink window-handle={video_window_handle}"
                else:  # YUYV
                    caps = f"video/x-raw,format=YUY2,width={w},height={h},framerate={self.current_fps}/1"
                    pipeline_str = f"v4l2src device={self.current_device} ! {caps} ! videoconvert ! xvimagesink window-handle={video_window_handle}"
            else:
                # Fallback to separate window
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
            self.status_label.set_markup(f"<span font='20' color='green'><b>Running: {self.current_device} {self.current_format} {w}x{h}@{self.current_fps}fps</b></span>")

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.status_label.set_markup(f"<span font='20' color='red'><b>Error: {e}</b></span>")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_markup("<span font='20'><b>Camera Stopped</b></span>")

if __name__ == "__main__":
    app = CameraWithLayout()
    Gtk.main()