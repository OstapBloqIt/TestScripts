#!/usr/bin/env python3
# touch_cam.py
# Wayland-friendly, touch-first USB camera viewer for Verdin i.MX8M Mini
# Features: on-screen controls, resolution 320x240..1920x1080, fps 0..60, exit, CPU/RAM usage
# Dependencies in container: python3-gi, gir1.2-gtk-4.0, gir1.2-gst-1.0, gstreamer1.0-plugins-{base,good,bad},
#                            gstreamer1.0-libav (optional), psutil (optional), v4l-utils (optional)

import gi
import os
import sys
import time

gi.require_version("Gtk", "4.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gio, GLib, Gst

# ----------------------------
# Simple CPU/MEM readers (no psutil needed)
# ----------------------------
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

# ----------------------------
# GStreamer + GTK App
# ----------------------------
class CamApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.ostap.touchcam", flags=Gio.ApplicationFlags.FLAGS_NONE)
        Gst.init(None)
        self.pipeline = None
        self.video_widget = None  # provided by gtksink
        self.device = os.environ.get('CAM_DEVICE', '/dev/video0')
        # Defaults
        self.width = 1280
        self.height = 720
        self.fps = 30
        self.paused = False

        # Supported resolutions (min..max)
        self.res_options = [
            (320, 240), (640, 480), (800, 600), (1280, 720), (1280, 800), (1366, 768), (1600, 900), (1920, 1080)
        ]

    # UI
    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("USB Cam — Touch Viewer")
        self.window.set_default_size(1280, 800)

        # Root: vertical box
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.window.set_child(root)

        # Video area (gtksink widget placeholder)
        self.video_area = Gtk.Box()
        self.video_area.set_hexpand(True)
        self.video_area.set_vexpand(True)
        self.video_area.add_css_class("card")
        root.append(self.video_area)

        # Controls row
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.add_css_class("toolbar")
        root.append(controls)

        # Resolution dropdown
        res_store = Gio.ListStore(item_type=Gio.SimpleAction)
        self.res_combo = Gtk.DropDown()
        self.res_combo.set_hexpand(False)
        # Build strings like "1280x720"
        self.res_strings = [f"{w}x{h}" for (w, h) in self.res_options]
        self.res_string_store = Gtk.StringList.new(self.res_strings)
        self.res_combo.set_model(self.res_string_store)
        # Default select closest to default width/height
        try:
            idx = self.res_strings.index(f"{self.width}x{self.height}")
        except ValueError:
            idx = len(self.res_strings) - 1
        self.res_combo.set_selected(idx)
        self.res_combo.connect("notify::selected", self.on_resolution_changed)
        controls.append(Gtk.Label(label="Resolution:"))
        controls.append(self.res_combo)

        # FPS slider 0..60
        self.fps_adjust = Gtk.Adjustment(lower=0, upper=60, step_increment=1, page_increment=5, value=self.fps)
        self.fps_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.fps_adjust)
        self.fps_scale.set_hexpand(True)
        self.fps_scale.set_digits(0)
        self.fps_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.fps_scale.connect("value-changed", self.on_fps_changed)
        controls.append(Gtk.Label(label="FPS:"))
        controls.append(self.fps_scale)

        # Pause/Play
        self.pause_btn = Gtk.Button(label="Pause")
        self.pause_btn.add_css_class("pill")
        self.pause_btn.set_size_request(120, 48)
        self.pause_btn.connect("clicked", self.on_toggle_pause)
        controls.append(self.pause_btn)

        # Restart pipeline
        self.restart_btn = Gtk.Button(label="Apply")
        self.restart_btn.set_size_request(120, 48)
        self.restart_btn.connect("clicked", self.on_apply)
        controls.append(self.restart_btn)

        # Exit
        self.exit_btn = Gtk.Button(label="Exit")
        self.exit_btn.add_css_class("destructive-action")
        self.exit_btn.set_size_request(120, 48)
        self.exit_btn.connect("clicked", lambda *_: self.window.close())
        controls.append(self.exit_btn)

        # Resource usage
        self.usage_label = Gtk.Label(label="CPU 0% | RAM 0%")
        self.usage_label.set_xalign(1.0)
        controls.append(self.usage_label)

        # Start pipeline
        self.build_pipeline()

        # Update resource label every 500 ms
        GLib.timeout_add(500, self.update_usage)

        self.window.present()

    # Build/Attach GStreamer pipeline with gtksink
    def build_pipeline(self):
        # Tear down existing
        if self.pipeline:
            try:
                self.pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            self.pipeline = None

        # Create elements
        self.pipeline = Gst.Pipeline.new("touchcam-pipeline")
        v4l2 = Gst.ElementFactory.make("v4l2src", "src")
        if not v4l2:
            self.alert("Missing gstreamer v4l2src. Install gstreamer1.0-plugins-good.")
            return
        v4l2.set_property("device", self.device)

        capsfilter = Gst.ElementFactory.make("capsfilter", "caps")
        # Compose caps for resolution + fps
        fps = int(self.fps)
        if fps <= 0:
            fps = 1  # will immediately pause pipeline below
        caps = Gst.Caps.from_string(f"video/x-raw, width={self.width}, height={self.height}, framerate={fps}/1")
        capsfilter.set_property("caps", caps)

        convert = Gst.ElementFactory.make("videoconvert", "convert")
        scale = Gst.ElementFactory.make("videoscale", "scale")
        rate = Gst.ElementFactory.make("videorate", "rate")

        # Sink that gives us a GTK widget (works on Wayland)
        gtksink = Gst.ElementFactory.make("gtksink", "sink")
        if not gtksink:
            # Fallback to autovideosink if gtksink is missing (not embeddable)
            gtksink = Gst.ElementFactory.make("autovideosink", "sink")

        for el in [v4l2, rate, scale, convert, capsfilter, gtksink]:
            self.pipeline.add(el)
        if not Gst.Element.link_many(v4l2, rate, scale, convert, capsfilter, gtksink):
            self.alert("Failed to link GStreamer elements.")
            return

        # Embed video widget if gtksink
        if gtksink.get_name() == "sink" and gtksink.get_factory().get_name() == "gtksink":
            widget = gtksink.props.widget
            if widget:
                widget.set_hexpand(True)
                widget.set_vexpand(True)
                # Replace previous child if any
                for child in self.video_area.get_children():
                    self.video_area.remove(child)
                self.video_area.append(widget)

        # Start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        if int(self.fps) == 0:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.paused = True
            self.pause_btn.set_label("Play")
        else:
            self.paused = False
            self.pause_btn.set_label("Pause")

        # Watch for bus errors
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self.on_gst_error)
        bus.connect("message::state-changed", self.on_state_changed)

    # Handlers
    def on_resolution_changed(self, combo, _pspec):
        idx = combo.get_selected()
        if idx < 0 or idx >= len(self.res_options):
            return
        self.width, self.height = self.res_options[idx]

    def on_fps_changed(self, scale):
        self.fps = int(scale.get_value())

    def on_toggle_pause(self, _btn):
        if not self.pipeline:
            return
        self.paused = not self.paused
        if self.paused:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pause_btn.set_label("Play")
        else:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.pause_btn.set_label("Pause")

    def on_apply(self, _btn):
        # Rebuild with new caps
        self.build_pipeline()

    def on_gst_error(self, bus, msg):
        err, debug = msg.parse_error()
        self.alert(f"GStreamer error: {err}\n{debug or ''}")

    def on_state_changed(self, bus, msg):
        if msg.src == self.pipeline:
            old, new, pending = msg.parse_state_changed()
            # Could update UI here if desired

    def update_usage(self):
        cpu = read_cpu_percent()
        mem = read_mem_percent()
        self.usage_label.set_text(f"CPU {cpu:.0f}% | RAM {mem:.0f}%")
        return True  # keep timer

    def alert(self, text):
        dlg = Gtk.AlertDialog(text=text)
        dlg.set_modal(True)
        dlg.show(self.window)


def main():
    app = CamApp()
    return app.run(sys.argv)

if __name__ == '__main__':
    raise SystemExit(main())

# ----------------------------
# Dockerfile (save as Dockerfile in same folder)
# ----------------------------
# Example base: Debian or Torizon Python Wayland base
# FROM torizon/wayland-base:3-bullseye  # if using Torizon
# Alternatively, generic Debian:
# FROM debian:bookworm
# RUN apt-get update && apt-get install -y \
#     python3 python3-gi gir1.2-gtk-4.0 gir1.2-gst-1.0 \
#     gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
#     gstreamer1.0-plugins-bad gstreamer1.0-libav v4l-utils \
#     && rm -rf /var/lib/apt/lists/*
# ENV PYTHONUNBUFFERED=1 \
#     WAYLAND_DISPLAY=wayland-0
# WORKDIR /app
# COPY touch_cam.py /app/
# CMD ["python3", "/app/touch_cam.py"]

# ----------------------------
# docker-compose.yml snippet
# ----------------------------
# services:
#   touch-cam:
#     build: .
#     environment:
#       - WAYLAND_DISPLAY=wayland-0
#       - CAM_DEVICE=/dev/video0
#     devices:
#       - "/dev/video0:/dev/video0"
#     volumes:
#       - "/tmp/wayland-0:/tmp/wayland-0"   # adjust if your Weston socket is elsewhere
#     network_mode: "host"                    # optional
#     ipc: "host"
#     restart: unless-stopped
