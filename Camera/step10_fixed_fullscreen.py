#!/usr/bin/env python3
# Step 10: Camera app with fixed fullscreen toggle

import gi
import glob
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib

class CameraFixedFullscreen(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 10: Camera with Fixed Fullscreen")

        # Track fullscreen state
        self.is_fullscreen = False

        # Start in fullscreen for your 1280x800 rotated display
        self.setup_window_fullscreen()

        self.connect("destroy", Gtk.main_quit)
        # Connect to window state events to track fullscreen properly
        self.connect("window-state-event", self.on_window_state_event)

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

    def setup_window_fullscreen(self):
        """Setup window for fullscreen mode"""
        self.set_default_size(800, 1280)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.fullscreen()
        self.is_fullscreen = True

    def setup_window_windowed(self):
        """Setup window for windowed mode"""
        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)

    def on_window_state_event(self, widget, event):
        """Handle window state changes"""
        if event.new_window_state & Gtk.gdk.WindowState.FULLSCREEN:
            self.is_fullscreen = True
        else:
            self.is_fullscreen = False
        return False

    def setup_layout(self):
        # Main vertical box - adjusts based on fullscreen/windowed
        main_vbox = Gtk.VBox(spacing=0)
        self.add(main_vbox)

        # Controls area - size depends on fullscreen state
        controls_frame = Gtk.Frame()
        if self.is_fullscreen:
            controls_frame.set_size_request(800, 400)
        else:
            controls_frame.set_size_request(800, 200)
        controls_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(controls_frame, False, False, 0)

        # Controls container with padding
        controls_vbox = Gtk.VBox(spacing=10)
        controls_vbox.set_property("margin", 15)
        controls_frame.add(controls_vbox)

        # Status label
        self.status_label = Gtk.Label(label="Camera Ready")
        self.status_label.set_markup("<span font='18'><b>Camera Ready</b></span>")
        controls_vbox.pack_start(self.status_label, False, False, 0)

        # Controls row 1: Device and Format
        hbox1 = Gtk.HBox(spacing=15)
        controls_vbox.pack_start(hbox1, False, False, 0)

        device_label = Gtk.Label(label="Device:")
        device_label.set_markup("<span font='14'>Device:</span>")
        hbox1.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.current_device)
        self.device_btn.set_size_request(180, 40)
        self.device_btn.connect("clicked", self.cycle_device)
        hbox1.pack_start(self.device_btn, False, False, 0)

        format_label = Gtk.Label(label="Format:")
        format_label.set_markup("<span font='14'>Format:</span>")
        hbox1.pack_start(format_label, False, False, 0)

        self.format_btn = Gtk.Button(label=self.current_format)
        self.format_btn.set_size_request(100, 40)
        self.format_btn.connect("clicked", self.cycle_format)
        hbox1.pack_start(self.format_btn, False, False, 0)

        # Controls row 2: Resolution and FPS
        hbox2 = Gtk.HBox(spacing=15)
        controls_vbox.pack_start(hbox2, False, False, 0)

        res_label = Gtk.Label(label="Resolution:")
        res_label.set_markup("<span font='14'>Resolution:</span>")
        hbox2.pack_start(res_label, False, False, 0)

        self.res_btn = Gtk.Button(label="640x480")
        self.res_btn.set_size_request(130, 40)
        self.res_btn.connect("clicked", self.cycle_resolution)
        hbox2.pack_start(self.res_btn, False, False, 0)

        fps_label = Gtk.Label(label="FPS:")
        fps_label.set_markup("<span font='14'>FPS:</span>")
        hbox2.pack_start(fps_label, False, False, 0)

        self.fps_btn = Gtk.Button(label="30")
        self.fps_btn.set_size_request(70, 40)
        self.fps_btn.connect("clicked", self.cycle_fps)
        hbox2.pack_start(self.fps_btn, False, False, 0)

        # Control buttons row
        hbox3 = Gtk.HBox(spacing=15)
        controls_vbox.pack_start(hbox3, False, False, 0)

        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.set_size_request(180, 50)
        self.start_btn.connect("clicked", self.on_start_stop)
        hbox3.pack_start(self.start_btn, False, False, 0)

        # Fullscreen toggle button
        self.fullscreen_btn = Gtk.Button(label="Windowed")
        self.fullscreen_btn.set_size_request(100, 50)
        self.fullscreen_btn.connect("clicked", self.safe_toggle_fullscreen)
        hbox3.pack_start(self.fullscreen_btn, False, False, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(80, 50)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        hbox3.pack_start(exit_btn, False, False, 0)

        # Video info area
        video_frame = Gtk.Frame()
        if self.is_fullscreen:
            video_frame.set_size_request(800, 880)
        else:
            video_frame.set_size_request(800, 400)
        video_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(video_frame, True, True, 0)

        # Video info label
        self.video_info = Gtk.Label()
        self.video_info.set_markup("<span font='16'>Video will appear in separate window</span>")
        self.video_info.set_line_wrap(True)
        video_frame.add(self.video_info)

        self.show_all()

    def safe_toggle_fullscreen(self, btn):
        """Safely toggle fullscreen with proper cleanup"""
        try:
            # Stop camera if running to avoid conflicts
            was_running = self.is_running
            if self.is_running:
                self.stop_camera()

            # Small delay to let things settle
            GLib.timeout_add(100, self.do_fullscreen_toggle, btn, was_running)

        except Exception as e:
            print(f"Fullscreen toggle error: {e}")

    def do_fullscreen_toggle(self, btn, restart_camera):
        """Actually perform the fullscreen toggle"""
        try:
            if self.is_fullscreen:
                # Going to windowed
                self.unfullscreen()
                self.setup_window_windowed()
                btn.set_label("Fullscreen")
                self.is_fullscreen = False
            else:
                # Going to fullscreen
                self.fullscreen()
                btn.set_label("Windowed")
                self.is_fullscreen = True

            # Restart camera if it was running
            if restart_camera:
                GLib.timeout_add(200, self.restart_camera_after_toggle)

        except Exception as e:
            print(f"Fullscreen toggle execution error: {e}")

        return False  # Don't repeat timeout

    def restart_camera_after_toggle(self):
        """Restart camera after fullscreen toggle"""
        self.start_camera()
        return False  # Don't repeat timeout

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

            # Simple pipeline without positioning hints
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
            self.status_label.set_markup(f"<span font='18' color='green'><b>Running: {self.current_device} {self.current_format} {w}x{h}@{self.current_fps}fps</b></span>")
            self.video_info.set_markup(f"<span font='16' color='blue'><b>Video playing in separate window\n{self.current_format} {w}x{h} @ {self.current_fps}fps</b></span>")

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.status_label.set_markup(f"<span font='18' color='red'><b>Error: {e}</b></span>")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_markup("<span font='18'><b>Camera Stopped</b></span>")
        self.video_info.set_markup("<span font='16'>Video will appear in separate window</span>")

if __name__ == "__main__":
    app = CameraFixedFullscreen()
    Gtk.main()