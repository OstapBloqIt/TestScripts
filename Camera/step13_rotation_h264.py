#!/usr/bin/env python3
# Step 13: Camera with 180-degree rotation and H.264 support

import gi
import glob
import subprocess
import re
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib

class CameraRotationH264(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 13: Camera with Rotation & H.264")

        # Fixed window size for rotated display
        self.set_default_size(800, 1280)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None
        self.is_running = False

        # Find video devices and their capabilities
        self.video_devices = self.get_video_devices_with_caps()
        self.current_device_info = self.video_devices[0] if self.video_devices else None

        # Rotation options
        self.rotations = [0, 90, 180, 270]
        self.current_rotation = 180  # Start with 180 degrees

        self.setup_layout()

    def get_video_devices_with_caps(self):
        """Get video devices and determine their capabilities"""
        devices = []

        for device_path in glob.glob('/dev/video*'):
            try:
                # Try to get device capabilities
                result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                                      capture_output=True, text=True, timeout=3)

                device_info = {'path': device_path, 'formats': [], 'resolutions': []}

                if result.returncode == 0 and result.stdout.strip():
                    # Parse formats
                    if 'H264' in result.stdout:
                        device_info['formats'] = ['H264']
                        device_info['resolutions'] = [(640, 480), (800, 600), (1280, 720), (1920, 1080)]
                    elif 'MJPG' in result.stdout or 'YUYV' in result.stdout:
                        device_info['formats'] = ['MJPG', 'YUYV']
                        device_info['resolutions'] = [(640, 480), (800, 600), (1280, 720), (1920, 1080)]

                    if device_info['formats']:  # Only add devices with formats
                        devices.append(device_info)

            except Exception as e:
                print(f"Error checking {device_path}: {e}")
                continue

        # Fallback if no devices found
        if not devices:
            devices = [{'path': '/dev/video2', 'formats': ['MJPG', 'YUYV'], 'resolutions': [(640, 480), (800, 600)]}]

        return devices

    def setup_layout(self):
        # Main vertical box
        main_vbox = Gtk.VBox(spacing=0)
        self.add(main_vbox)

        # Controls area
        controls_frame = Gtk.Frame()
        controls_frame.set_size_request(800, 450)  # Bigger for more controls
        controls_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(controls_frame, False, False, 0)

        # Controls container
        controls_vbox = Gtk.VBox(spacing=15)
        controls_vbox.set_property("margin", 20)
        controls_frame.add(controls_vbox)

        # Status label
        self.status_label = Gtk.Label(label="Camera Ready")
        self.status_label.set_markup("<span font='18'><b>Camera Ready</b></span>")
        controls_vbox.pack_start(self.status_label, False, False, 0)

        # Controls row 1: Device and Format
        hbox1 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox1, False, False, 0)

        device_label = Gtk.Label(label="Device:")
        device_label.set_markup("<span font='14'>Device:</span>")
        hbox1.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.current_device_info['path'] if self.current_device_info else "/dev/video2")
        self.device_btn.set_size_request(180, 45)
        self.device_btn.connect("clicked", self.cycle_device)
        hbox1.pack_start(self.device_btn, False, False, 0)

        format_label = Gtk.Label(label="Format:")
        format_label.set_markup("<span font='14'>Format:</span>")
        hbox1.pack_start(format_label, False, False, 0)

        self.format_btn = Gtk.Button(label=self.current_device_info['formats'][0] if self.current_device_info else "MJPG")
        self.format_btn.set_size_request(100, 45)
        self.format_btn.connect("clicked", self.cycle_format)
        hbox1.pack_start(self.format_btn, False, False, 0)

        # Controls row 2: Resolution and Rotation
        hbox2 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox2, False, False, 0)

        res_label = Gtk.Label(label="Resolution:")
        res_label.set_markup("<span font='14'>Resolution:</span>")
        hbox2.pack_start(res_label, False, False, 0)

        self.res_btn = Gtk.Button(label="640x480")
        self.res_btn.set_size_request(130, 45)
        self.res_btn.connect("clicked", self.cycle_resolution)
        hbox2.pack_start(self.res_btn, False, False, 0)

        rotation_label = Gtk.Label(label="Rotation:")
        rotation_label.set_markup("<span font='14'>Rotation:</span>")
        hbox2.pack_start(rotation_label, False, False, 0)

        self.rotation_btn = Gtk.Button(label="180°")
        self.rotation_btn.set_size_request(80, 45)
        self.rotation_btn.connect("clicked", self.cycle_rotation)
        hbox2.pack_start(self.rotation_btn, False, False, 0)

        # Controls row 3: FPS and Controls
        hbox3 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox3, False, False, 0)

        fps_label = Gtk.Label(label="FPS:")
        fps_label.set_markup("<span font='14'>FPS:</span>")
        hbox3.pack_start(fps_label, False, False, 0)

        self.fps_btn = Gtk.Button(label="30")
        self.fps_btn.set_size_request(70, 45)
        self.fps_btn.connect("clicked", self.cycle_fps)
        hbox3.pack_start(self.fps_btn, False, False, 0)

        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.set_size_request(180, 50)
        self.start_btn.connect("clicked", self.on_start_stop)
        hbox3.pack_start(self.start_btn, False, False, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(80, 50)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        hbox3.pack_start(exit_btn, False, False, 0)

        # Video info area
        video_frame = Gtk.Frame()
        video_frame.set_size_request(800, 830)
        video_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(video_frame, True, True, 0)

        # Video info label
        self.video_info = Gtk.Label()
        self.update_device_info()
        video_frame.add(self.video_info)

        self.show_all()

        # Initialize current values
        self.current_format = self.current_device_info['formats'][0] if self.current_device_info else 'MJPG'
        self.current_resolution = (640, 480)
        self.fps_options = [15, 30, 60]
        self.current_fps = 30

    def update_device_info(self):
        """Update the device info display"""
        if self.current_device_info:
            info_text = f"<span font='16'><b>Device:</b> {self.current_device_info['path']}\n"
            info_text += f"<b>Formats:</b> {', '.join(self.current_device_info['formats'])}\n"
            info_text += f"<b>Rotation:</b> {self.current_rotation}°\n\n"
            info_text += "Video will appear in separate window</span>"
        else:
            info_text = "<span font='16'>No video devices found</span>"

        self.video_info.set_markup(info_text)

    def cycle_device(self, btn):
        try:
            current_idx = next((i for i, d in enumerate(self.video_devices) if d['path'] == self.current_device_info['path']), 0)
            next_idx = (current_idx + 1) % len(self.video_devices)
            self.current_device_info = self.video_devices[next_idx]

            btn.set_label(self.current_device_info['path'])

            # Update format button for new device
            self.current_format = self.current_device_info['formats'][0]
            self.format_btn.set_label(self.current_format)

            self.update_device_info()

        except Exception as e:
            print(f"Device cycle error: {e}")

    def cycle_format(self, btn):
        try:
            if self.current_device_info:
                formats = self.current_device_info['formats']
                current_idx = formats.index(self.current_format) if self.current_format in formats else 0
                next_idx = (current_idx + 1) % len(formats)
                self.current_format = formats[next_idx]
                btn.set_label(self.current_format)
        except Exception as e:
            print(f"Format cycle error: {e}")

    def cycle_resolution(self, btn):
        try:
            if self.current_device_info:
                resolutions = self.current_device_info['resolutions']
                current_idx = resolutions.index(self.current_resolution) if self.current_resolution in resolutions else 0
                next_idx = (current_idx + 1) % len(resolutions)
                self.current_resolution = resolutions[next_idx]
                w, h = self.current_resolution
                btn.set_label(f"{w}x{h}")
        except Exception as e:
            print(f"Resolution cycle error: {e}")

    def cycle_rotation(self, btn):
        try:
            current_idx = self.rotations.index(self.current_rotation)
            next_idx = (current_idx + 1) % len(self.rotations)
            self.current_rotation = self.rotations[next_idx]
            btn.set_label(f"{self.current_rotation}°")
            self.update_device_info()
        except Exception as e:
            print(f"Rotation cycle error: {e}")

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
            if not self.current_device_info:
                self.status_label.set_markup("<span font='18' color='red'><b>No device available</b></span>")
                return

            device_path = self.current_device_info['path']
            w, h = self.current_resolution

            # Build pipeline based on format and rotation
            if self.current_format == 'H264':
                # H.264 pipeline
                caps = f"video/x-h264,width={w},height={h},framerate={self.current_fps}/1"
                if self.current_rotation == 0:
                    pipeline_str = f"v4l2src device={device_path} ! {caps} ! h264parse ! avdec_h264 ! videoconvert ! waylandsink"
                else:
                    pipeline_str = f"v4l2src device={device_path} ! {caps} ! h264parse ! avdec_h264 ! videoconvert ! videoflip method={self.get_flip_method()} ! waylandsink"

            elif self.current_format == 'MJPG':
                # MJPG pipeline
                caps = f"image/jpeg,width={w},height={h},framerate={self.current_fps}/1"
                if self.current_rotation == 0:
                    pipeline_str = f"v4l2src device={device_path} ! {caps} ! jpegdec ! videoconvert ! waylandsink"
                else:
                    pipeline_str = f"v4l2src device={device_path} ! {caps} ! jpegdec ! videoconvert ! videoflip method={self.get_flip_method()} ! waylandsink"

            else:  # YUYV
                caps = f"video/x-raw,format=YUY2,width={w},height={h},framerate={self.current_fps}/1"
                if self.current_rotation == 0:
                    pipeline_str = f"v4l2src device={device_path} ! {caps} ! videoconvert ! waylandsink"
                else:
                    pipeline_str = f"v4l2src device={device_path} ! {caps} ! videoconvert ! videoflip method={self.get_flip_method()} ! waylandsink"

            print(f"Pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.status_label.set_markup(f"<span font='18' color='green'><b>Running: {device_path} {self.current_format} {w}x{h}@{self.current_fps}fps</b></span>")

            info_text = f"<span font='16' color='blue'><b>Video playing with {self.current_rotation}° rotation\n"
            info_text += f"{self.current_format} {w}x{h} @ {self.current_fps}fps\n"
            info_text += f"Device: {device_path}</b></span>"
            self.video_info.set_markup(info_text)

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.status_label.set_markup(f"<span font='18' color='red'><b>Error: {e}</b></span>")

    def get_flip_method(self):
        """Get GStreamer videoflip method for rotation"""
        rotation_methods = {
            0: 0,    # none
            90: 1,   # clockwise-90
            180: 2,  # rotate-180
            270: 3   # counterclockwise-90
        }
        return rotation_methods.get(self.current_rotation, 2)

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_markup("<span font='18'><b>Camera Stopped</b></span>")
        self.update_device_info()

if __name__ == "__main__":
    app = CameraRotationH264()
    Gtk.main()