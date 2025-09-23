#!/usr/bin/env python3
# test_subprocess.py - Test if subprocess calls are the culprit
import gi
import subprocess
import glob
import re

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gdk, Gst, GLib

Gdk.set_allowed_backends("wayland")

def get_video_devices():
    print("Getting video devices...")
    devices = []
    for device_path in glob.glob('/dev/video*'):
        device_num = int(re.findall(r'\d+', device_path)[-1])
        if device_num >= 2:
            try:
                with open(device_path, 'rb') as f:
                    devices.append(device_path)
            except:
                pass
    print(f"Found devices: {devices}")
    return sorted(devices) if devices else ['/dev/video2']

def get_device_formats(device_path):
    print(f"Getting formats for {device_path}")
    try:
        # THIS subprocess call might be the issue
        result = subprocess.run(['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            formats = []
            for line in result.stdout.split('\n'):
                match = re.search(r"\[(\d+)\]:\s+'([^']+)'\s+\(([^)]+)\)", line)
                if match:
                    code, desc = match.group(2), match.group(3)
                    formats.append((code, f"{code} ({desc})"))
            print(f"Detected formats: {formats}")
            return formats if formats else [('MJPG', 'MJPG (Motion-JPEG)')]
    except Exception as e:
        print(f"Format detection failed: {e}")
    return [('MJPG', 'MJPG (Motion-JPEG)'), ('YUYV', 'YUYV (YUV 4:2:2)')]

class TestSubprocessWindow(Gtk.Window):
    def __init__(self):
        print("Creating window with subprocess calls...")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Test Subprocess")
        self.connect("destroy", Gtk.main_quit)

        self.set_default_size(800, 600)
        self.maximize()

        # These function calls include subprocess.run()
        print("Calling get_video_devices()...")
        self.video_devices = get_video_devices()

        print("Calling get_device_formats()...")
        self.available_formats = get_device_formats(self.video_devices[0])

        vbox = Gtk.VBox(spacing=8)
        self.add(vbox)

        label = Gtk.Label(label=f"Found {len(self.video_devices)} devices, {len(self.available_formats)} formats")
        vbox.pack_start(label, True, True, 0)

        btn = Gtk.Button(label="Test")
        vbox.pack_start(btn, False, False, 0)

        print("Showing window...")
        self.show_all()
        print("Window shown successfully")

if __name__ == "__main__":
    print("Testing subprocess calls...")
    app = TestSubprocessWindow()
    print("Entering main loop...")
    Gtk.main()