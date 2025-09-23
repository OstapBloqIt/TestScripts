#!/usr/bin/env python3
# GTK3 version of touch camera app for Verdin i.MX8M Mini
# Features: device selector, format detection, resolution controls, fps adjustment

import os
import gi
import sys
import time
import subprocess
import glob
import re

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gst

# Force Wayland backend like the working pattern app
Gdk.set_allowed_backends("wayland")

_prev_total = 0
_prev_idle = 0

def read_cpu_percent():
    global _prev_total, _prev_idle
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        parts = [float(x) for x in line.split()[1:8]]
        user, nice, system, idle, iowait, irq, softirq = parts
        idle_all = idle + iowait
        non_idle = user + nice + system + irq + softirq
        total = idle_all + non_idle
        if _prev_total == 0:
            _prev_total, _prev_idle = total, idle_all
            return 0.0
        totald = total - _prev_total
        idled = idle_all - _prev_idle
        _prev_total, _prev_idle = total, idle_all
        if totald <= 0:
            return 0.0
        return max(0.0, min(100.0, (totald - idled) * 100.0 / totald))
    except Exception:
        return 0.0

def read_mem_percent():
    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                key, val = line.split(':', 1)
                meminfo[key.strip()] = int(val.strip().split()[0])  # kB
        total = meminfo.get('MemTotal', 1)
        free = meminfo.get('MemFree', 0) + meminfo.get('Buffers', 0) + meminfo.get('Cached', 0)
        used = max(0, total - free)
        return used * 100.0 / total
    except Exception:
        return 0.0

def get_video_devices():
    """Get available video devices starting from /dev/video2"""
    devices = []
    for device_path in glob.glob('/dev/video*'):
        device_num = int(re.findall(r'\d+', device_path)[-1])
        if device_num >= 2:  # Skip /dev/video0 and /dev/video1 (GPU modules)
            try:
                result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-devices'],
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    devices.append(device_path)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                try:
                    with open(device_path, 'rb') as f:
                        devices.append(device_path)
                except (PermissionError, OSError):
                    pass
    return sorted(devices)

def get_device_formats(device_path):
    """Get supported formats for a video device"""
    formats = []
    try:
        result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                format_match = re.search(r"\[(\d+)\]:\s+'([^']+)'\s+\(([^)]+)\)", line)
                if format_match:
                    format_code = format_match.group(2)
                    format_desc = format_match.group(3)
                    current_format = f"{format_code} ({format_desc})"
                    formats.append((format_code, current_format))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        formats = [
            ('MJPG', 'MJPG (Motion-JPEG)'),
            ('YUYV', 'YUYV (YUV 4:2:2)'),
            ('YUV420', 'YUV420 (YUV 4:2:0)'),
            ('H264', 'H264 (H.264 compressed)')
        ]

    if not formats:
        formats = [
            ('MJPG', 'MJPG (Motion-JPEG)'),
            ('YUYV', 'YUYV (YUV 4:2:2)')
        ]

    return formats

class CameraWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("USB Camera Touch Viewer")
        self.fullscreen()
        self.connect("destroy", Gtk.main_quit)

        # Initialize GStreamer
        Gst.init(None)
        self.pipeline = None

        # Get available video devices (starting from /dev/video2)
        self.video_devices = get_video_devices()
        default_device = self.video_devices[0] if self.video_devices else '/dev/video2'
        self.device = os.environ.get('CAM_DEVICE', default_device)

        if self.device not in self.video_devices and self.video_devices:
            self.device = self.video_devices[0]

        self.width = 1280
        self.height = 720
        self.fps = 30
        self.paused = False
        self.current_format = 'MJPG'
        self.available_formats = []

        self.res_options = [
            (320, 240), (640, 480), (800, 600), (1280, 720), (1280, 800),
            (1366, 768), (1600, 900), (1920, 1080)
        ]

        self.setup_ui()
        self.update_formats()
        self.build_pipeline()

        # Start usage monitoring
        GLib.timeout_add(500, self.update_usage)

    def setup_ui(self):
        # Main container
        vbox = Gtk.VBox(spacing=8)
        vbox.set_margin_left(12)
        vbox.set_margin_right(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.add(vbox)

        # Video area
        self.video_area = Gtk.Box()
        self.video_area.set_hexpand(True)
        self.video_area.set_vexpand(True)
        vbox.pack_start(self.video_area, True, True, 0)

        # Controls
        controls = Gtk.HBox(spacing=8)
        vbox.pack_start(controls, False, False, 0)

        # Device selector
        controls.pack_start(Gtk.Label("Device:"), False, False, 0)
        self.device_combo = Gtk.ComboBoxText()
        device_list = self.video_devices if self.video_devices else ['/dev/video2']
        for device in device_list:
            self.device_combo.append_text(device)
        try:
            idx = device_list.index(self.device)
            self.device_combo.set_active(idx)
        except ValueError:
            self.device_combo.set_active(0)
        self.device_combo.connect("changed", self.on_device_changed)
        controls.pack_start(self.device_combo, False, False, 0)

        # Format selector
        controls.pack_start(Gtk.Label("Format:"), False, False, 0)
        self.format_combo = Gtk.ComboBoxText()
        self.format_combo.connect("changed", self.on_format_changed)
        controls.pack_start(self.format_combo, False, False, 0)

        # Resolution selector
        controls.pack_start(Gtk.Label("Resolution:"), False, False, 0)
        self.res_combo = Gtk.ComboBoxText()
        for w, h in self.res_options:
            self.res_combo.append_text(f"{w}x{h}")
        try:
            idx = [f"{w}x{h}" for w, h in self.res_options].index(f"{self.width}x{self.height}")
            self.res_combo.set_active(idx)
        except ValueError:
            self.res_combo.set_active(-1)
        self.res_combo.connect("changed", self.on_resolution_changed)
        controls.pack_start(self.res_combo, False, False, 0)

        # FPS scale
        controls.pack_start(Gtk.Label("FPS:"), False, False, 0)
        self.fps_scale = Gtk.HScale()
        self.fps_scale.set_range(0, 60)
        self.fps_scale.set_value(self.fps)
        self.fps_scale.set_digits(0)
        self.fps_scale.set_size_request(150, -1)
        self.fps_scale.connect("value-changed", self.on_fps_changed)
        controls.pack_start(self.fps_scale, True, True, 0)

        # Control buttons
        self.pause_btn = Gtk.Button(label="Pause")
        self.pause_btn.set_size_request(80, 40)
        self.pause_btn.connect("clicked", self.on_toggle_pause)
        controls.pack_start(self.pause_btn, False, False, 0)

        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.set_size_request(80, 40)
        self.apply_btn.connect("clicked", self.on_apply)
        controls.pack_start(self.apply_btn, False, False, 0)

        self.exit_btn = Gtk.Button(label="Exit")
        self.exit_btn.set_size_request(80, 40)
        self.exit_btn.connect("clicked", lambda *_: Gtk.main_quit())
        controls.pack_start(self.exit_btn, False, False, 0)

        # Usage label
        self.usage_label = Gtk.Label("CPU 0% | RAM 0%")
        self.usage_label.set_alignment(1.0, 0.5)
        controls.pack_start(self.usage_label, False, False, 0)

        self.show_all()

    def update_formats(self):
        """Update the format dropdown based on current device"""
        self.available_formats = get_device_formats(self.device)

        self.format_combo.remove_all()
        for code, desc in self.available_formats:
            self.format_combo.append_text(desc)

        # Select current format or default to first
        selected_idx = 0
        for i, (code, desc) in enumerate(self.available_formats):
            if code == self.current_format:
                selected_idx = i
                break

        if self.available_formats:
            self.format_combo.set_active(selected_idx)
            self.current_format = self.available_formats[selected_idx][0]

    def on_device_changed(self, combo):
        """Handle video device selection change"""
        idx = combo.get_active()
        device_list = self.video_devices if self.video_devices else ['/dev/video2']
        if idx >= 0 and idx < len(device_list):
            self.device = device_list[idx]
            self.update_formats()

    def on_format_changed(self, combo):
        """Handle format selection change"""
        idx = combo.get_active()
        if idx >= 0 and idx < len(self.available_formats):
            self.current_format = self.available_formats[idx][0]

    def on_resolution_changed(self, combo):
        idx = combo.get_active()
        if idx >= 0 and idx < len(self.res_options):
            self.width, self.height = self.res_options[idx]

    def on_fps_changed(self, scale):
        self.fps = int(scale.get_value())

    def on_toggle_pause(self, btn):
        if not self.pipeline:
            return
        self.paused = not self.paused
        if self.paused:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pause_btn.set_label("Play")
        else:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.pause_btn.set_label("Pause")

    def on_apply(self, btn):
        self.build_pipeline()

    def build_pipeline(self):
        if self.pipeline:
            try:
                self.pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            self.pipeline = None

        self.pipeline = Gst.Pipeline.new("camera-pipeline")
        v4l2 = Gst.ElementFactory.make("v4l2src", "src")
        if not v4l2:
            self.show_error("Missing gstreamer v4l2src. Install gstreamer1.0-plugins-good.")
            return
        v4l2.set_property("device", self.device)

        # Build pipeline based on selected format
        fps = int(self.fps) if self.fps > 0 else 1
        elements = []

        if self.current_format == 'MJPG':
            capsfilter1 = Gst.ElementFactory.make("capsfilter", "caps1")
            caps1 = Gst.Caps.from_string(f"image/jpeg, width={self.width}, height={self.height}, framerate={fps}/1")
            capsfilter1.set_property("caps", caps1)
            jpegdec = Gst.ElementFactory.make("jpegdec", "jpegdec")
            elements.extend([capsfilter1, jpegdec])
        elif self.current_format == 'H264':
            capsfilter1 = Gst.ElementFactory.make("capsfilter", "caps1")
            caps1 = Gst.Caps.from_string(f"video/x-h264, width={self.width}, height={self.height}, framerate={fps}/1")
            capsfilter1.set_property("caps", caps1)
            h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
            avdec_h264 = Gst.ElementFactory.make("avdec_h264", "avdec_h264")
            elements.extend([capsfilter1, h264parse, avdec_h264])
        else:
            # Raw formats
            capsfilter1 = Gst.ElementFactory.make("capsfilter", "caps1")
            format_mapping = {
                'YUYV': 'video/x-raw, format=YUY2',
                'YUV420': 'video/x-raw, format=I420',
                'UYVY': 'video/x-raw, format=UYVY',
                'RGB': 'video/x-raw, format=RGB'
            }
            format_string = format_mapping.get(self.current_format, 'video/x-raw')
            caps1 = Gst.Caps.from_string(f"{format_string}, width={self.width}, height={self.height}, framerate={fps}/1")
            capsfilter1.set_property("caps", caps1)
            elements.append(capsfilter1)

        convert = Gst.ElementFactory.make("videoconvert", "convert")
        scale = Gst.ElementFactory.make("videoscale", "scale")
        rate = Gst.ElementFactory.make("videorate", "rate")

        # Final caps filter for output
        capsfilter2 = Gst.ElementFactory.make("capsfilter", "caps2")
        caps2 = Gst.Caps.from_string(f"video/x-raw, width={self.width}, height={self.height}, framerate={fps}/1")
        capsfilter2.set_property("caps", caps2)

        # Try gtksink first, fallback to autovideosink
        sink = Gst.ElementFactory.make("gtksink", "sink")
        if not sink:
            sink = Gst.ElementFactory.make("autovideosink", "sink")

        # Add all elements to pipeline
        all_elements = [v4l2] + elements + [rate, scale, convert, capsfilter2, sink]
        for el in all_elements:
            if el:
                self.pipeline.add(el)

        # Link elements in sequence
        prev_element = v4l2
        for element in elements + [rate, scale, convert, capsfilter2, sink]:
            if element and not prev_element.link(element):
                self.show_error(f"Failed to link {prev_element.get_name()} → {element.get_name()}")
                return
            prev_element = element

        # Try to embed gtksink widget
        if sink.get_factory().get_name() == "gtksink":
            widget = sink.props.widget
            if widget:
                widget.set_hexpand(True)
                widget.set_vexpand(True)
                # Clear video area and add widget
                for child in self.video_area.get_children():
                    self.video_area.remove(child)
                self.video_area.pack_start(widget, True, True, 0)
                widget.show()

        # Start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        if int(self.fps) == 0:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.paused = True
            self.pause_btn.set_label("Play")
        else:
            self.paused = False
            self.pause_btn.set_label("Pause")

        # Connect bus signals
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self.on_gst_error)

    def on_gst_error(self, bus, msg):
        err, debug = msg.parse_error()
        message = f"GStreamer error: {err}\n{debug or ''}"
        self.show_error(message)

    def update_usage(self):
        cpu = read_cpu_percent()
        mem = read_mem_percent()
        self.usage_label.set_text(f"CPU {cpu:.0f}% | RAM {mem:.0f}%")
        return True

    def show_error(self, text):
        print(text, file=sys.stderr)
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error",
            secondary_text=str(text)
        )
        dialog.run()
        dialog.destroy()

if __name__ == '__main__':
    app = CameraWindow()
    Gtk.main()