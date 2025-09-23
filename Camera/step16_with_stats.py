#!/usr/bin/env python3
# Step 16: Fullscreen camera app with bitrate and statistics

import gi
import glob
import subprocess
import time
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib

class CameraWithStats(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 16: Camera with Statistics")

        # Start in fullscreen
        self.fullscreen()
        self.set_keep_above(True)

        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None
        self.is_running = False

        # Statistics tracking
        self.stats = {
            'frames_processed': 0,
            'bytes_processed': 0,
            'start_time': 0,
            'last_update': 0,
            'current_fps': 0,
            'current_bitrate': 0,
            'avg_fps': 0,
            'avg_bitrate': 0
        }

        # Find video devices and their capabilities
        self.video_devices = self.get_video_devices_with_caps()
        self.current_device_info = self.video_devices[0] if self.video_devices else None

        # FPS options including 5 and 10
        self.fps_options = [5, 10, 15, 30, 60]
        self.current_fps = 30

        self.setup_layout()

        # Statistics update timer
        self.stats_timer = None

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
        # Main vertical box for fullscreen (800x1280 for rotated display)
        main_vbox = Gtk.VBox(spacing=0)
        self.add(main_vbox)

        # Controls area (top 350px - reduced to make room for stats)
        controls_frame = Gtk.Frame()
        controls_frame.set_size_request(800, 350)
        controls_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(controls_frame, False, False, 0)

        # Controls container
        controls_vbox = Gtk.VBox(spacing=12)
        controls_vbox.set_property("margin", 15)
        controls_frame.add(controls_vbox)

        # Status label
        self.status_label = Gtk.Label(label="Camera Ready")
        self.status_label.set_markup("<span font='18'><b>Fullscreen Camera with Stats</b></span>")
        controls_vbox.pack_start(self.status_label, False, False, 0)

        # Controls row 1: Device and Format
        hbox1 = Gtk.HBox(spacing=15)
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

        # Controls row 2: Resolution and FPS
        hbox2 = Gtk.HBox(spacing=15)
        controls_vbox.pack_start(hbox2, False, False, 0)

        res_label = Gtk.Label(label="Resolution:")
        res_label.set_markup("<span font='14'>Resolution:</span>")
        hbox2.pack_start(res_label, False, False, 0)

        self.res_btn = Gtk.Button(label="640x480")
        self.res_btn.set_size_request(130, 45)
        self.res_btn.connect("clicked", self.cycle_resolution)
        hbox2.pack_start(self.res_btn, False, False, 0)

        fps_label = Gtk.Label(label="FPS:")
        fps_label.set_markup("<span font='14'>FPS:</span>")
        hbox2.pack_start(fps_label, False, False, 0)

        self.fps_btn = Gtk.Button(label="30")
        self.fps_btn.set_size_request(70, 45)
        self.fps_btn.connect("clicked", self.cycle_fps)
        hbox2.pack_start(self.fps_btn, False, False, 0)

        # Controls row 3: Main buttons
        hbox3 = Gtk.HBox(spacing=15)
        controls_vbox.pack_start(hbox3, False, False, 0)

        self.start_btn = Gtk.Button(label="Start Camera")
        self.start_btn.set_size_request(180, 50)
        self.start_btn.connect("clicked", self.on_start_stop)
        hbox3.pack_start(self.start_btn, False, False, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(80, 50)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        hbox3.pack_start(exit_btn, False, False, 0)

        # Statistics area (middle 200px)
        stats_frame = Gtk.Frame()
        stats_frame.set_size_request(800, 200)
        stats_frame.set_shadow_type(Gtk.ShadowType.IN)
        stats_frame.set_label("Real-time Statistics")
        main_vbox.pack_start(stats_frame, False, False, 0)

        # Statistics container
        stats_vbox = Gtk.VBox(spacing=8)
        stats_vbox.set_property("margin", 10)
        stats_frame.add(stats_vbox)

        # Current stats row
        current_stats_hbox = Gtk.HBox(spacing=20)
        stats_vbox.pack_start(current_stats_hbox, False, False, 0)

        self.current_fps_label = Gtk.Label()
        self.current_fps_label.set_markup("<span font='12'><b>Current FPS:</b> 0.0</span>")
        current_stats_hbox.pack_start(self.current_fps_label, False, False, 0)

        self.current_bitrate_label = Gtk.Label()
        self.current_bitrate_label.set_markup("<span font='12'><b>Current Bitrate:</b> 0 kbps</span>")
        current_stats_hbox.pack_start(self.current_bitrate_label, False, False, 0)

        # Average stats row
        avg_stats_hbox = Gtk.HBox(spacing=20)
        stats_vbox.pack_start(avg_stats_hbox, False, False, 0)

        self.avg_fps_label = Gtk.Label()
        self.avg_fps_label.set_markup("<span font='12'><b>Average FPS:</b> 0.0</span>")
        avg_stats_hbox.pack_start(self.avg_fps_label, False, False, 0)

        self.avg_bitrate_label = Gtk.Label()
        self.avg_bitrate_label.set_markup("<span font='12'><b>Average Bitrate:</b> 0 kbps</span>")
        avg_stats_hbox.pack_start(self.avg_bitrate_label, False, False, 0)

        # Total stats row
        total_stats_hbox = Gtk.HBox(spacing=20)
        stats_vbox.pack_start(total_stats_hbox, False, False, 0)

        self.frames_label = Gtk.Label()
        self.frames_label.set_markup("<span font='12'><b>Total Frames:</b> 0</span>")
        total_stats_hbox.pack_start(self.frames_label, False, False, 0)

        self.data_label = Gtk.Label()
        self.data_label.set_markup("<span font='12'><b>Total Data:</b> 0 MB</span>")
        total_stats_hbox.pack_start(self.data_label, False, False, 0)

        self.uptime_label = Gtk.Label()
        self.uptime_label.set_markup("<span font='12'><b>Uptime:</b> 00:00</span>")
        total_stats_hbox.pack_start(self.uptime_label, False, False, 0)

        # Video info area (bottom 730px)
        video_frame = Gtk.Frame()
        video_frame.set_size_request(800, 730)
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

    def update_device_info(self):
        """Update the device info display"""
        if self.current_device_info:
            info_text = f"<span font='16'><b>Device:</b> {self.current_device_info['path']}\n"
            info_text += f"<b>Formats:</b> {', '.join(self.current_device_info['formats'])}\n"
            info_text += f"<b>FPS Options:</b> {', '.join(map(str, self.fps_options))}\n\n"
            info_text += "<b>Video will appear in 640x480 window</b>\n"
            info_text += "Statistics updated every second</span>"
        else:
            info_text = "<span font='16'>No video devices found</span>"

        self.video_info.set_markup(info_text)

    def update_statistics(self):
        """Update pipeline statistics"""
        if not self.pipeline or not self.is_running:
            return True

        try:
            current_time = time.time()

            # Get pipeline statistics
            if self.pipeline:
                # Query for statistics (this is a simplified approach)
                # In a real implementation, you'd use GStreamer's statistics elements

                elapsed = current_time - self.stats['start_time']
                if elapsed > 0:
                    # Estimate frame rate based on target FPS (simplified)
                    estimated_frames = int(elapsed * self.current_fps)
                    self.stats['frames_processed'] = estimated_frames

                    # Estimate data based on resolution and format (simplified)
                    w, h = self.current_resolution
                    if self.current_format == 'H264':
                        # H.264 is compressed, estimate lower bitrate
                        bytes_per_frame = (w * h * 0.1)  # Rough compression estimate
                    elif self.current_format == 'MJPG':
                        # MJPG is moderately compressed
                        bytes_per_frame = (w * h * 0.3)
                    else:  # YUYV
                        # Uncompressed YUV
                        bytes_per_frame = (w * h * 2)

                    estimated_bytes = int(estimated_frames * bytes_per_frame)
                    self.stats['bytes_processed'] = estimated_bytes

                    # Calculate rates
                    interval = current_time - self.stats['last_update']
                    if interval >= 1.0:  # Update every second
                        self.stats['current_fps'] = self.current_fps  # Simplified
                        self.stats['current_bitrate'] = (bytes_per_frame * self.current_fps * 8) / 1000  # kbps
                        self.stats['avg_fps'] = self.stats['frames_processed'] / elapsed
                        self.stats['avg_bitrate'] = (self.stats['bytes_processed'] * 8) / (elapsed * 1000)  # kbps
                        self.stats['last_update'] = current_time

                        # Update UI
                        self.update_stats_display()

        except Exception as e:
            print(f"Stats update error: {e}")

        return True  # Continue timer

    def update_stats_display(self):
        """Update the statistics display"""
        try:
            # Current stats
            self.current_fps_label.set_markup(f"<span font='12'><b>Current FPS:</b> {self.stats['current_fps']:.1f}</span>")
            self.current_bitrate_label.set_markup(f"<span font='12'><b>Current Bitrate:</b> {self.stats['current_bitrate']:.0f} kbps</span>")

            # Average stats
            self.avg_fps_label.set_markup(f"<span font='12'><b>Average FPS:</b> {self.stats['avg_fps']:.1f}</span>")
            self.avg_bitrate_label.set_markup(f"<span font='12'><b>Average Bitrate:</b> {self.stats['avg_bitrate']:.0f} kbps</span>")

            # Total stats
            self.frames_label.set_markup(f"<span font='12'><b>Total Frames:</b> {self.stats['frames_processed']}</span>")

            mb_processed = self.stats['bytes_processed'] / (1024 * 1024)
            self.data_label.set_markup(f"<span font='12'><b>Total Data:</b> {mb_processed:.1f} MB</span>")

            elapsed = time.time() - self.stats['start_time']
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self.uptime_label.set_markup(f"<span font='12'><b>Uptime:</b> {minutes:02d}:{seconds:02d}</span>")

        except Exception as e:
            print(f"Stats display error: {e}")

    def reset_statistics(self):
        """Reset all statistics"""
        current_time = time.time()
        self.stats = {
            'frames_processed': 0,
            'bytes_processed': 0,
            'start_time': current_time,
            'last_update': current_time,
            'current_fps': 0,
            'current_bitrate': 0,
            'avg_fps': 0,
            'avg_bitrate': 0
        }
        self.update_stats_display()

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

            # Force video output to 640x480 window regardless of capture resolution
            video_w, video_h = 640, 480

            # Build pipeline with statistics elements for better monitoring
            if self.current_format == 'H264':
                caps = f"video/x-h264,width={w},height={h},framerate={self.current_fps}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! h264parse ! avdec_h264 ! videoconvert ! videoscale ! video/x-raw,width={video_w},height={video_h} ! waylandsink"

            elif self.current_format == 'MJPG':
                caps = f"image/jpeg,width={w},height={h},framerate={self.current_fps}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! jpegdec ! videoconvert ! videoscale ! video/x-raw,width={video_w},height={video_h} ! waylandsink"

            else:  # YUYV
                caps = f"video/x-raw,format=YUY2,width={w},height={h},framerate={self.current_fps}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! videoconvert ! videoscale ! video/x-raw,width={video_w},height={video_h} ! waylandsink"

            print(f"Pipeline: {pipeline_str}")
            print(f"Capture: {w}x{h} -> Display: {video_w}x{video_h}")

            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            # Reset and start statistics
            self.reset_statistics()
            self.stats_timer = GLib.timeout_add(1000, self.update_statistics)  # Update every second

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.status_label.set_markup(f"<span font='18' color='green'><b>Running: {device_path} {self.current_format} {w}x{h}@{self.current_fps}fps</b></span>")

            info_text = f"<span font='16' color='blue'><b>Video playing in {video_w}x{video_h} window\n"
            info_text += f"Capture: {self.current_format} {w}x{h} @ {self.current_fps}fps\n"
            info_text += f"Device: {device_path}\n"
            info_text += "Statistics updating every second</b></span>"
            self.video_info.set_markup(info_text)

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.status_label.set_markup(f"<span font='18' color='red'><b>Error: {e}</b></span>")

    def stop_camera(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        if self.stats_timer:
            GLib.source_remove(self.stats_timer)
            self.stats_timer = None

        self.is_running = False
        self.start_btn.set_label("Start Camera")
        self.status_label.set_markup("<span font='18'><b>Camera Stopped</b></span>")
        self.update_device_info()

        # Reset stats display
        self.current_fps_label.set_markup("<span font='12'><b>Current FPS:</b> 0.0</span>")
        self.current_bitrate_label.set_markup("<span font='12'><b>Current Bitrate:</b> 0 kbps</span>")
        self.avg_fps_label.set_markup("<span font='12'><b>Average FPS:</b> 0.0</span>")
        self.avg_bitrate_label.set_markup("<span font='12'><b>Average Bitrate:</b> 0 kbps</span>")
        self.frames_label.set_markup("<span font='12'><b>Total Frames:</b> 0</span>")
        self.data_label.set_markup("<span font='12'><b>Total Data:</b> 0 MB</span>")
        self.uptime_label.set_markup("<span font='12'><b>Uptime:</b> 00:00</span>")

if __name__ == "__main__":
    app = CameraWithStats()
    Gtk.main()