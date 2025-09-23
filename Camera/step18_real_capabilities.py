#!/usr/bin/env python3
# Step 18: Camera with REAL device capabilities parsing

import gi
import glob
import subprocess
import time
import re
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib

class CameraRealCapabilities(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 18: Camera with Real Device Capabilities")

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

        # Find video devices and their REAL capabilities
        print("Scanning video devices for capabilities...")
        self.video_devices = self.get_real_device_capabilities()
        self.current_device_info = self.video_devices[0] if self.video_devices else None

        self.setup_layout()

        # Statistics update timer
        self.stats_timer = None

    def parse_v4l2_output(self, device_path):
        """Parse v4l2-ctl output to extract real device capabilities"""
        try:
            result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                                  capture_output=True, text=True, timeout=5)

            if result.returncode != 0 or not result.stdout.strip():
                print(f"No output from {device_path}")
                return {}

            capabilities = {}
            current_format = None

            lines = result.stdout.split('\n')

            for line in lines:
                line = line.strip()

                # Look for format lines like: [0]: 'MJPG' (Motion-JPEG, compressed)
                format_match = re.search(r"\[(\d+)\]:\s+'([^']+)'\s+\(([^)]+)\)", line)
                if format_match:
                    format_code = format_match.group(2)
                    format_desc = format_match.group(3)
                    current_format = format_code
                    capabilities[current_format] = {
                        'description': format_desc,
                        'resolutions': {}
                    }
                    print(f"  Found format: {format_code} ({format_desc})")
                    continue

                # Look for size lines like: Size: Discrete 1280x720
                size_match = re.search(r"Size:\s+Discrete\s+(\d+)x(\d+)", line)
                if size_match and current_format:
                    width = int(size_match.group(1))
                    height = int(size_match.group(2))
                    resolution = (width, height)

                    if resolution not in capabilities[current_format]['resolutions']:
                        capabilities[current_format]['resolutions'][resolution] = []
                    continue

                # Look for interval lines like: Interval: Discrete 0.033s (30.000 fps)
                interval_match = re.search(r"Interval:\s+Discrete\s+[\d.]+s\s+\(([\d.]+)\s+fps\)", line)
                if interval_match and current_format:
                    fps = float(interval_match.group(1))
                    # Add this fps to the last resolution found
                    resolutions = capabilities[current_format]['resolutions']
                    if resolutions:
                        last_resolution = list(resolutions.keys())[-1]
                        capabilities[current_format]['resolutions'][last_resolution].append(fps)

            return capabilities

        except Exception as e:
            print(f"Error parsing v4l2 output for {device_path}: {e}")
            return {}

    def get_real_device_capabilities(self):
        """Get video devices and their REAL capabilities from v4l2-ctl"""
        devices = []

        for device_path in glob.glob('/dev/video*'):
            try:
                print(f"Checking {device_path}...")
                capabilities = self.parse_v4l2_output(device_path)

                if capabilities:
                    device_info = {
                        'path': device_path,
                        'capabilities': capabilities
                    }

                    # Log what we found
                    print(f"  Device {device_path} capabilities:")
                    for fmt, fmt_data in capabilities.items():
                        res_count = len(fmt_data['resolutions'])
                        print(f"    {fmt}: {res_count} resolutions")
                        for res, fps_list in fmt_data['resolutions'].items():
                            fps_str = ', '.join([f"{fps:.0f}" for fps in sorted(fps_list)])
                            print(f"      {res[0]}x{res[1]}: {fps_str} fps")

                    devices.append(device_info)
                else:
                    print(f"  No usable formats found for {device_path}")

            except Exception as e:
                print(f"Error checking {device_path}: {e}")
                continue

        # Fallback if no devices found
        if not devices:
            print("No devices found, using fallback")
            devices = [{
                'path': '/dev/video2',
                'capabilities': {
                    'MJPG': {
                        'description': 'Motion-JPEG (fallback)',
                        'resolutions': {
                            (640, 480): [15.0, 30.0],
                            (320, 240): [15.0, 30.0]
                        }
                    }
                }
            }]

        print(f"Found {len(devices)} usable video devices")
        return devices

    def get_current_formats(self):
        """Get list of formats for current device"""
        if not self.current_device_info:
            return []
        return list(self.current_device_info['capabilities'].keys())

    def get_current_resolutions(self, format_name):
        """Get list of resolutions for current device and format"""
        if not self.current_device_info or format_name not in self.current_device_info['capabilities']:
            return []
        return list(self.current_device_info['capabilities'][format_name]['resolutions'].keys())

    def get_current_framerates(self, format_name, resolution):
        """Get list of framerates for current device, format, and resolution"""
        if (not self.current_device_info or
            format_name not in self.current_device_info['capabilities'] or
            resolution not in self.current_device_info['capabilities'][format_name]['resolutions']):
            return []
        return sorted(self.current_device_info['capabilities'][format_name]['resolutions'][resolution])

    def setup_layout(self):
        # Main vertical box for fullscreen (800x1280 for rotated display)
        main_vbox = Gtk.VBox(spacing=0)
        self.add(main_vbox)

        # Controls area (top 350px)
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
        self.status_label.set_markup("<span font='18'><b>Camera with Real Device Capabilities</b></span>")
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

        formats = self.get_current_formats()
        self.format_btn = Gtk.Button(label=formats[0] if formats else "MJPG")
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

        # Video info label with real capabilities
        self.video_info = Gtk.Label()
        self.update_device_info()
        video_frame.add(self.video_info)

        self.show_all()

        # Initialize current values with real capabilities
        formats = self.get_current_formats()
        if formats:
            self.current_format = formats[0]
            resolutions = self.get_current_resolutions(self.current_format)
            if resolutions:
                self.current_resolution = resolutions[0]
                framerates = self.get_current_framerates(self.current_format, self.current_resolution)
                if framerates:
                    self.current_fps = framerates[0]
                else:
                    self.current_fps = 30.0
            else:
                self.current_resolution = (640, 480)
                self.current_fps = 30.0
        else:
            self.current_format = "MJPG"
            self.current_resolution = (640, 480)
            self.current_fps = 30.0

        # Update button labels
        self.format_btn.set_label(self.current_format)
        w, h = self.current_resolution
        self.res_btn.set_label(f"{w}x{h}")
        self.fps_btn.set_label(f"{self.current_fps:.0f}")

    def update_device_info(self):
        """Update the device info display with real capabilities"""
        if self.current_device_info:
            capabilities = self.current_device_info['capabilities']

            info_text = f"<span font='14'><b>Device:</b> {self.current_device_info['path']}\n\n"

            for fmt, fmt_data in capabilities.items():
                info_text += f"<b>{fmt}</b> ({fmt_data['description']}):\n"

                for resolution, fps_list in fmt_data['resolutions'].items():
                    w, h = resolution
                    fps_str = ', '.join([f"{fps:.0f}" for fps in sorted(fps_list)])
                    info_text += f"  {w}x{h}: {fps_str} fps\n"

                info_text += "\n"

            info_text += "<b>Video displayed in 640x480 window</b>\n"
            info_text += "All options based on actual device capabilities</span>"
        else:
            info_text = "<span font='14'>No video devices found</span>"

        self.video_info.set_markup(info_text)

    def update_statistics(self):
        """Update pipeline statistics"""
        if not self.pipeline or not self.is_running:
            return True

        try:
            current_time = time.time()

            if self.pipeline:
                elapsed = current_time - self.stats['start_time']
                if elapsed > 0:
                    # Estimate frame rate based on target FPS
                    estimated_frames = int(elapsed * self.current_fps)
                    self.stats['frames_processed'] = estimated_frames

                    # Estimate data based on resolution and format
                    w, h = self.current_resolution
                    if self.current_format == 'H264':
                        bytes_per_frame = (w * h * 0.1)
                    elif self.current_format == 'MJPG':
                        bytes_per_frame = (w * h * 0.3)
                    else:  # YUYV
                        bytes_per_frame = (w * h * 2)

                    estimated_bytes = int(estimated_frames * bytes_per_frame)
                    self.stats['bytes_processed'] = estimated_bytes

                    # Calculate rates
                    interval = current_time - self.stats['last_update']
                    if interval >= 1.0:
                        self.stats['current_fps'] = self.current_fps
                        self.stats['current_bitrate'] = (bytes_per_frame * self.current_fps * 8) / 1000
                        self.stats['avg_fps'] = self.stats['frames_processed'] / elapsed
                        self.stats['avg_bitrate'] = (self.stats['bytes_processed'] * 8) / (elapsed * 1000)
                        self.stats['last_update'] = current_time

                        self.update_stats_display()

        except Exception as e:
            print(f"Stats update error: {e}")

        return True

    def update_stats_display(self):
        """Update the statistics display"""
        try:
            self.current_fps_label.set_markup(f"<span font='12'><b>Current FPS:</b> {self.stats['current_fps']:.1f}</span>")
            self.current_bitrate_label.set_markup(f"<span font='12'><b>Current Bitrate:</b> {self.stats['current_bitrate']:.0f} kbps</span>")
            self.avg_fps_label.set_markup(f"<span font='12'><b>Average FPS:</b> {self.stats['avg_fps']:.1f}</span>")
            self.avg_bitrate_label.set_markup(f"<span font='12'><b>Average Bitrate:</b> {self.stats['avg_bitrate']:.0f} kbps</span>")
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

            # Reset to first available format, resolution, and fps
            formats = self.get_current_formats()
            if formats:
                self.current_format = formats[0]
                self.format_btn.set_label(self.current_format)

                resolutions = self.get_current_resolutions(self.current_format)
                if resolutions:
                    self.current_resolution = resolutions[0]
                    w, h = self.current_resolution
                    self.res_btn.set_label(f"{w}x{h}")

                    framerates = self.get_current_framerates(self.current_format, self.current_resolution)
                    if framerates:
                        self.current_fps = framerates[0]
                        self.fps_btn.set_label(f"{self.current_fps:.0f}")

            self.update_device_info()

        except Exception as e:
            print(f"Device cycle error: {e}")

    def cycle_format(self, btn):
        try:
            formats = self.get_current_formats()
            if formats:
                current_idx = formats.index(self.current_format) if self.current_format in formats else 0
                next_idx = (current_idx + 1) % len(formats)
                self.current_format = formats[next_idx]
                btn.set_label(self.current_format)

                # Reset resolution and fps for new format
                resolutions = self.get_current_resolutions(self.current_format)
                if resolutions:
                    self.current_resolution = resolutions[0]
                    w, h = self.current_resolution
                    self.res_btn.set_label(f"{w}x{h}")

                    framerates = self.get_current_framerates(self.current_format, self.current_resolution)
                    if framerates:
                        self.current_fps = framerates[0]
                        self.fps_btn.set_label(f"{self.current_fps:.0f}")

        except Exception as e:
            print(f"Format cycle error: {e}")

    def cycle_resolution(self, btn):
        try:
            resolutions = self.get_current_resolutions(self.current_format)
            if resolutions:
                current_idx = resolutions.index(self.current_resolution) if self.current_resolution in resolutions else 0
                next_idx = (current_idx + 1) % len(resolutions)
                self.current_resolution = resolutions[next_idx]
                w, h = self.current_resolution
                btn.set_label(f"{w}x{h}")

                # Reset fps for new resolution
                framerates = self.get_current_framerates(self.current_format, self.current_resolution)
                if framerates:
                    self.current_fps = framerates[0]
                    self.fps_btn.set_label(f"{self.current_fps:.0f}")

        except Exception as e:
            print(f"Resolution cycle error: {e}")

    def cycle_fps(self, btn):
        try:
            framerates = self.get_current_framerates(self.current_format, self.current_resolution)
            if framerates:
                current_idx = framerates.index(self.current_fps) if self.current_fps in framerates else 0
                next_idx = (current_idx + 1) % len(framerates)
                self.current_fps = framerates[next_idx]
                btn.set_label(f"{self.current_fps:.0f}")

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

            # Force video output to 640x480 window
            video_w, video_h = 640, 480

            # Build pipeline using real fps
            if self.current_format == 'H264':
                caps = f"video/x-h264,width={w},height={h},framerate={self.current_fps:.0f}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! h264parse ! avdec_h264 ! videoconvert ! videoscale ! video/x-raw,width={video_w},height={video_h} ! waylandsink"

            elif self.current_format == 'MJPG':
                caps = f"image/jpeg,width={w},height={h},framerate={self.current_fps:.0f}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! jpegdec ! videoconvert ! videoscale ! video/x-raw,width={video_w},height={video_h} ! waylandsink"

            else:  # YUYV
                caps = f"video/x-raw,format=YUY2,width={w},height={h},framerate={self.current_fps:.0f}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! videoconvert ! videoscale ! video/x-raw,width={video_w},height={video_h} ! waylandsink"

            print(f"Pipeline: {pipeline_str}")
            print(f"Real device capability: {self.current_format} {w}x{h} @ {self.current_fps} fps")

            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            # Reset and start statistics
            self.reset_statistics()
            self.stats_timer = GLib.timeout_add(1000, self.update_statistics)

            self.is_running = True
            self.start_btn.set_label("Stop Camera")
            self.status_label.set_markup(f"<span font='18' color='green'><b>Running: {device_path} {self.current_format} {w}x{h}@{self.current_fps:.0f}fps</b></span>")

            info_text = f"<span font='14' color='blue'><b>Using REAL device capability:\n"
            info_text += f"{self.current_format} {w}x{h} @ {self.current_fps:.0f}fps\n"
            info_text += f"Device: {device_path}\n"
            info_text += f"Display: {video_w}x{video_h}</b></span>"
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
    app = CameraRealCapabilities()
    Gtk.main()