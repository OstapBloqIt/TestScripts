#!/usr/bin/env python3
# Step 19: Camera video recorder - Records 15-second videos to files

import gi
import glob
import subprocess
import time
import re
import os
from datetime import datetime
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib

class CameraVideoRecorder(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("Step 19: Camera Video Recorder")

        # Start in fullscreen
        self.fullscreen()
        self.set_keep_above(True)

        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None
        self.is_recording = False
        self.recording_timer = None
        self.record_start_time = 0

        # Recording settings
        self.recording_duration = 15  # seconds
        self.output_base_dir = "recordings"

        # Statistics tracking
        self.stats = {
            'recordings_made': 0,
            'total_duration': 0,
            'last_file_path': '',
            'last_file_size': 0
        }

        # Find video devices and their REAL capabilities
        print("Scanning video devices for capabilities...")
        self.video_devices = self.get_real_device_capabilities()
        self.current_device_info = self.video_devices[0] if self.video_devices else None

        self.setup_layout()
        self.create_output_directories()

    def parse_v4l2_output(self, device_path):
        """Parse v4l2-ctl output to extract real device capabilities"""
        try:
            result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                                  capture_output=True, text=True, timeout=5)

            if result.returncode != 0 or not result.stdout.strip():
                return {}

            capabilities = {}
            current_format = None

            lines = result.stdout.split('\n')

            for line in lines:
                line = line.strip()

                # Look for format lines
                format_match = re.search(r"\[(\d+)\]:\s+'([^']+)'\s+\(([^)]+)\)", line)
                if format_match:
                    format_code = format_match.group(2)
                    format_desc = format_match.group(3)
                    current_format = format_code
                    capabilities[current_format] = {
                        'description': format_desc,
                        'resolutions': {}
                    }
                    continue

                # Look for size lines
                size_match = re.search(r"Size:\s+Discrete\s+(\d+)x(\d+)", line)
                if size_match and current_format:
                    width = int(size_match.group(1))
                    height = int(size_match.group(2))
                    resolution = (width, height)

                    if resolution not in capabilities[current_format]['resolutions']:
                        capabilities[current_format]['resolutions'][resolution] = []
                    continue

                # Look for interval lines
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
                    devices.append(device_info)

            except Exception as e:
                print(f"Error checking {device_path}: {e}")
                continue

        # Fallback if no devices found
        if not devices:
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

    def create_output_directories(self):
        """Create output directories for each format"""
        try:
            if not os.path.exists(self.output_base_dir):
                os.makedirs(self.output_base_dir)

            for device_info in self.video_devices:
                for format_name in device_info['capabilities'].keys():
                    format_dir = os.path.join(self.output_base_dir, format_name.lower())
                    if not os.path.exists(format_dir):
                        os.makedirs(format_dir)
                        print(f"Created directory: {format_dir}")

        except Exception as e:
            print(f"Error creating directories: {e}")

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

    def generate_filename(self):
        """Generate filename based on current settings"""
        device_name = self.current_device_info['path'].replace('/dev/', '')
        w, h = self.current_resolution
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Determine file extension based on format
        if self.current_format == 'H264':
            ext = 'mp4'
        elif self.current_format == 'MJPG':
            ext = 'avi'
        else:  # YUYV
            ext = 'avi'

        filename = f"{device_name}_{self.current_format}_{w}x{h}_{self.current_fps:.0f}fps_{timestamp}.{ext}"

        format_dir = os.path.join(self.output_base_dir, self.current_format.lower())
        return os.path.join(format_dir, filename)

    def setup_layout(self):
        # Main vertical box for fullscreen
        main_vbox = Gtk.VBox(spacing=0)
        self.add(main_vbox)

        # Controls area (top 400px)
        controls_frame = Gtk.Frame()
        controls_frame.set_size_request(800, 400)
        controls_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(controls_frame, False, False, 0)

        # Controls container
        controls_vbox = Gtk.VBox(spacing=15)
        controls_vbox.set_property("margin", 20)
        controls_frame.add(controls_vbox)

        # Status label
        self.status_label = Gtk.Label(label="Video Recorder Ready")
        self.status_label.set_markup("<span font='20'><b>15-Second Video Recorder</b></span>")
        controls_vbox.pack_start(self.status_label, False, False, 0)

        # Controls row 1: Device and Format
        hbox1 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox1, False, False, 0)

        device_label = Gtk.Label(label="Device:")
        device_label.set_markup("<span font='16'>Device:</span>")
        hbox1.pack_start(device_label, False, False, 0)

        self.device_btn = Gtk.Button(label=self.current_device_info['path'] if self.current_device_info else "/dev/video2")
        self.device_btn.set_size_request(200, 50)
        self.device_btn.connect("clicked", self.cycle_device)
        hbox1.pack_start(self.device_btn, False, False, 0)

        format_label = Gtk.Label(label="Format:")
        format_label.set_markup("<span font='16'>Format:</span>")
        hbox1.pack_start(format_label, False, False, 0)

        formats = self.get_current_formats()
        self.format_btn = Gtk.Button(label=formats[0] if formats else "MJPG")
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

        # Controls row 3: Recording controls
        hbox3 = Gtk.HBox(spacing=20)
        controls_vbox.pack_start(hbox3, False, False, 0)

        self.record_btn = Gtk.Button(label="Record 15s Video")
        self.record_btn.set_size_request(200, 60)
        self.record_btn.connect("clicked", self.on_record)
        hbox3.pack_start(self.record_btn, False, False, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(100, 60)
        exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        hbox3.pack_start(exit_btn, False, False, 0)

        # Recording info area (middle 200px)
        info_frame = Gtk.Frame()
        info_frame.set_size_request(800, 200)
        info_frame.set_shadow_type(Gtk.ShadowType.IN)
        info_frame.set_label("Recording Information")
        main_vbox.pack_start(info_frame, False, False, 0)

        # Info container
        info_vbox = Gtk.VBox(spacing=10)
        info_vbox.set_property("margin", 15)
        info_frame.add(info_vbox)

        # Recording stats
        self.recording_info_label = Gtk.Label()
        self.recording_info_label.set_markup("<span font='14'><b>Ready to record</b></span>")
        info_vbox.pack_start(self.recording_info_label, False, False, 0)

        self.countdown_label = Gtk.Label()
        self.countdown_label.set_markup("<span font='18'></span>")
        info_vbox.pack_start(self.countdown_label, False, False, 0)

        self.stats_label = Gtk.Label()
        self.update_stats_display()
        info_vbox.pack_start(self.stats_label, False, False, 0)

        # Device info area (bottom)
        device_frame = Gtk.Frame()
        device_frame.set_size_request(800, 680)
        device_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(device_frame, True, True, 0)

        # Device info label
        self.device_info = Gtk.Label()
        self.update_device_info()
        device_frame.add(self.device_info)

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
        """Update the device info display"""
        if self.current_device_info:
            capabilities = self.current_device_info['capabilities']

            info_text = f"<span font='14'><b>Device:</b> {self.current_device_info['path']}\n"
            info_text += f"<b>Output Directory:</b> {self.output_base_dir}/\n\n"

            for fmt, fmt_data in capabilities.items():
                info_text += f"<b>{fmt}</b> → {fmt.lower()}/ folder:\n"

                for resolution, fps_list in fmt_data['resolutions'].items():
                    w, h = resolution
                    fps_str = ', '.join([f"{fps:.0f}" for fps in sorted(fps_list)])
                    info_text += f"  {w}x{h}: {fps_str} fps\n"

                info_text += "\n"

            info_text += "<b>Files will be named:</b>\n"
            info_text += "device_FORMAT_WIDTHxHEIGHT_FPSfps_TIMESTAMP.ext</span>"
        else:
            info_text = "<span font='14'>No video devices found</span>"

        self.device_info.set_markup(info_text)

    def update_stats_display(self):
        """Update the recording statistics display"""
        stats_text = f"<span font='12'><b>Total Recordings:</b> {self.stats['recordings_made']}\n"
        stats_text += f"<b>Total Duration:</b> {self.stats['total_duration']} seconds\n"

        if self.stats['last_file_path']:
            file_size_mb = self.stats['last_file_size'] / (1024 * 1024)
            stats_text += f"<b>Last File:</b> {os.path.basename(self.stats['last_file_path'])}\n"
            stats_text += f"<b>Last Size:</b> {file_size_mb:.2f} MB"

        stats_text += "</span>"
        self.stats_label.set_markup(stats_text)

    def cycle_device(self, btn):
        try:
            if self.is_recording:
                return  # Don't allow changes during recording

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
            if self.is_recording:
                return

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
            if self.is_recording:
                return

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
            if self.is_recording:
                return

            framerates = self.get_current_framerates(self.current_format, self.current_resolution)
            if framerates:
                current_idx = framerates.index(self.current_fps) if self.current_fps in framerates else 0
                next_idx = (current_idx + 1) % len(framerates)
                self.current_fps = framerates[next_idx]
                btn.set_label(f"{self.current_fps:.0f}")

        except Exception as e:
            print(f"FPS cycle error: {e}")

    def on_record(self, btn):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        try:
            if not self.current_device_info:
                self.status_label.set_markup("<span font='20' color='red'><b>No device available</b></span>")
                return

            device_path = self.current_device_info['path']
            w, h = self.current_resolution
            output_file = self.generate_filename()

            print(f"Recording to: {output_file}")

            # Build recording pipeline
            if self.current_format == 'H264':
                caps = f"video/x-h264,width={w},height={h},framerate={self.current_fps:.0f}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! h264parse ! mp4mux ! filesink location={output_file}"

            elif self.current_format == 'MJPG':
                caps = f"image/jpeg,width={w},height={h},framerate={self.current_fps:.0f}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! avimux ! filesink location={output_file}"

            else:  # YUYV
                caps = f"video/x-raw,format=YUY2,width={w},height={h},framerate={self.current_fps:.0f}/1"
                pipeline_str = f"v4l2src device={device_path} ! {caps} ! videoconvert ! x264enc ! avimux ! filesink location={output_file}"

            print(f"Pipeline: {pipeline_str}")

            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            self.is_recording = True
            self.record_start_time = time.time()
            self.stats['last_file_path'] = output_file

            self.record_btn.set_label("Recording...")
            self.record_btn.set_sensitive(False)

            # Disable controls during recording
            self.device_btn.set_sensitive(False)
            self.format_btn.set_sensitive(False)
            self.res_btn.set_sensitive(False)
            self.fps_btn.set_sensitive(False)

            self.status_label.set_markup(f"<span font='20' color='red'><b>● RECORDING: {os.path.basename(output_file)}</b></span>")
            self.recording_info_label.set_markup(f"<span font='14' color='red'><b>Recording: {self.current_format} {w}x{h}@{self.current_fps:.0f}fps</b></span>")

            # Start countdown timer
            self.recording_timer = GLib.timeout_add(100, self.update_recording_progress)

            # Auto-stop after 15 seconds
            GLib.timeout_add(self.recording_duration * 1000, self.stop_recording)

        except Exception as e:
            print(f"Recording error: {e}")
            self.status_label.set_markup(f"<span font='20' color='red'><b>Recording Error: {e}</b></span>")
            self.stop_recording()

    def update_recording_progress(self):
        """Update recording progress display"""
        if not self.is_recording:
            return False

        elapsed = time.time() - self.record_start_time
        remaining = max(0, self.recording_duration - elapsed)

        self.countdown_label.set_markup(f"<span font='18' color='red'><b>⏱ {remaining:.1f}s remaining</b></span>")

        return True  # Continue timer

    def stop_recording(self):
        """Stop recording and update statistics"""
        if not self.is_recording:
            return False

        if self.pipeline:
            # Send EOS to properly finish the file
            self.pipeline.send_event(Gst.Event.new_eos())

            # Wait a moment for EOS to process
            time.sleep(0.5)

            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

        if self.recording_timer:
            GLib.source_remove(self.recording_timer)
            self.recording_timer = None

        # Update statistics
        self.stats['recordings_made'] += 1
        self.stats['total_duration'] += self.recording_duration

        # Get file size
        if os.path.exists(self.stats['last_file_path']):
            self.stats['last_file_size'] = os.path.getsize(self.stats['last_file_path'])
            file_size_mb = self.stats['last_file_size'] / (1024 * 1024)
            print(f"Recording complete: {self.stats['last_file_path']} ({file_size_mb:.2f} MB)")
        else:
            self.stats['last_file_size'] = 0
            print("Recording failed - file not found")

        self.is_recording = False

        # Re-enable controls
        self.record_btn.set_label("Record 15s Video")
        self.record_btn.set_sensitive(True)
        self.device_btn.set_sensitive(True)
        self.format_btn.set_sensitive(True)
        self.res_btn.set_sensitive(True)
        self.fps_btn.set_sensitive(True)

        self.status_label.set_markup("<span font='20' color='green'><b>✓ Recording Complete</b></span>")
        self.recording_info_label.set_markup("<span font='14'><b>Ready to record next video</b></span>")
        self.countdown_label.set_markup("")

        self.update_stats_display()

        return False  # Stop the auto-stop timer

if __name__ == "__main__":
    app = CameraVideoRecorder()
    Gtk.main()