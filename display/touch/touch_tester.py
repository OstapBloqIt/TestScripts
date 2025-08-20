#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# GTK3 + Cairo + Wayland touch test utility
# Author: your overqualified code goblin

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GObject, GLib

import math
import time
import csv
import os
import random
import argparse
import cairo
from collections import deque

def now_ms():
    return int(time.time() * 1000)

def color_for_id(i):
    random.seed(i * 1337)
    return (0.3 + 0.7*random.random(), 0.3 + 0.7*random.random(), 0.3 + 0.7*random.random())

class TouchPoint:
    __slots__ = ("seq", "id", "x", "y", "start_ms", "last_ms", "trail", "pressure")
    def __init__(self, seq, tid, x, y, pressure=None):
        self.seq = seq
        self.id = tid
        self.x = x
        self.y = y
        self.start_ms = now_ms()
        self.last_ms = self.start_ms
        self.trail = deque(maxlen=1024)
        self.trail.append((x, y))
        self.pressure = pressure

class TouchTester(Gtk.Window):
    def __init__(self, args):
        Gtk.Window.__init__(self, title="Touch Tester: GTK3 + Cairo + Wayland")
        self.set_default_size(1024, 600)
        self.set_app_paintable(True)
        self.connect("delete-event", Gtk.main_quit)

        self.fullscreen_mode = args.fullscreen
        if self.fullscreen_mode:
            self.fullscreen()

        self.grid_on = True
        self.edge_mode = False
        self.tap_mode = False
        self.pinch_hud = True
        self.logging_on = bool(args.log)
        self.log_path = args.log
        self.log_fp = None
        self.csv = None

        # Drawing area
        self.da = Gtk.DrawingArea()
        self.da.set_size_request(400, 300)
        self.da.add_events(
            Gdk.EventMask.TOUCH_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.SMOOTH_SCROLL_MASK |
            Gdk.EventMask.KEY_PRESS_MASK |
            Gdk.EventMask.STRUCTURE_MASK |
            Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.da.set_can_focus(True)
        self.add(self.da)

        # Signals
        self.connect("key-press-event", self.on_key)
        self.da.connect("draw", self.on_draw)
        self.da.connect("touch-event", self.on_touch)
        # Mouse fallback as "seq=None"
        self.da.connect("button-press-event", self.on_mouse_press)
        self.da.connect("motion-notify-event", self.on_mouse_motion)
        self.da.connect("button-release-event", self.on_mouse_release)

        # Touch tracking
        self.next_touch_id = 1
        self.active = {}          # sequence -> TouchPoint
        self.dead_trails = []     # completed trails to keep drawing faintly

        # FPS + latency
        self.frame_times = deque(maxlen=120)
        self.fps = 0.0
        self.lat_samples = deque(maxlen=200)
        self.avg_latency_ms = 0

        # Pinch/rotate
        self.pinch_baseline = None  # (cx, cy, dist, angle)
        self.pinch_live = None      # (scale, deg)

        # Tap targets
        self.tap_targets = []
        self.tap_hits = 0
        self.tap_misses = 0
        self.target_radius = 28
        self.targets_count = 6

        # Edge coverage
        self.edge_thickness_ratio = 0.06
        self.edge_touched = {"top": False, "right": False, "bottom": False, "left": False}

        # Timer for repaint
        GLib.timeout_add(8, self.on_tick)  # ~60 Hz

        if self.logging_on:
            self.open_log()

        self.show_all()
        self.da.grab_focus()

    def open_log(self):
        try:
            self.log_fp = open(self.log_path, "w", newline="")
            self.csv = csv.writer(self.log_fp)
            self.csv.writerow(["timestamp_ms", "event", "seq_id", "x", "y", "pressure"])
        except Exception as e:
            print("Failed to open log file:", e)
            self.logging_on = False

    def close_log(self):
        if self.log_fp:
            self.log_fp.close()
            self.log_fp = None
            self.csv = None

    # ---------- Event handlers ----------
    def on_tick(self):
        self.queue_draw()
        return True

    def on_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "Escape":
            Gtk.main_quit()
            return True
        if key in ("f", "F"):
            if self.fullscreen_mode:
                self.unfullscreen()
                self.fullscreen_mode = False
            else:
                self.fullscreen()
                self.fullscreen_mode = True
            return True
        if key in ("g", "G"):
            self.grid_on = not self.grid_on
            return True
        if key in ("e", "E"):
            self.edge_mode = not self.edge_mode
            return True
        if key in ("t", "T"):
            self.tap_mode = not self.tap_mode
            if self.tap_mode and not self.tap_targets:
                self.spawn_targets()
            return True
        if key in ("p", "P"):
            self.pinch_hud = not self.pinch_hud
            return True
        if key in ("c", "C"):
            self.active.clear()
            self.dead_trails.clear()
            self.lat_samples.clear()
            self.avg_latency_ms = 0
            self.tap_hits = 0
            self.tap_misses = 0
            self.edge_touched = {k: False for k in self.edge_touched}
            self.pinch_baseline = None
            self.pinch_live = None
            return True
        if key in ("l", "L"):
            self.logging_on = not self.logging_on
            if self.logging_on and not self.csv:
                self.open_log()
            elif not self.logging_on and self.csv:
                self.close_log()
            return True
        return False

    def on_mouse_press(self, widget, event):
        # Treat mouse as a single touch with seq=None
        self._begin_touch(None, event.x, event.y, pressure=None)
        self._log("MOUSE_BEGIN", None, event.x, event.y, None)
        return True

    def on_mouse_motion(self, widget, event):
        if None in self.active:
            tp = self.active[None]
            tp.x, tp.y = event.x, event.y
            tp.last_ms = now_ms()
            tp.trail.append((tp.x, tp.y))
            self._log("MOUSE_UPDATE", None, tp.x, tp.y, None)
        return True

    def on_mouse_release(self, widget, event):
        if None in self.active:
            self._end_touch(None)
            self._log("MOUSE_END", None, event.x, event.y, None)
        return True

    def on_touch(self, widget, event):
        et = event.type
        seq = event.get_event_sequence()
        x, y = event.x, event.y

        # Try to guess pressure if exposed
        pressure = None
        try:
            # Some backends expose axes on touch events
            ok, p = event.get_axis(Gdk.AxisUse.PRESSURE)
            if ok:
                pressure = float(p)
        except Exception:
            pass

        if et == Gdk.EventType.TOUCH_BEGIN:
            self._begin_touch(seq, x, y, pressure)
            self._log("TOUCH_BEGIN", id(seq), x, y, pressure)
        elif et == Gdk.EventType.TOUCH_UPDATE:
            tp = self.active.get(seq)
            if not tp:
                # Occasionally UPDATE before BEGIN if backend is spicy; create on the fly
                self._begin_touch(seq, x, y, pressure)
            else:
                tp.x, tp.y = x, y
                tp.last_ms = now_ms()
                tp.trail.append((tp.x, tp.y))
                if pressure is not None:
                    tp.pressure = pressure
            self._log("TOUCH_UPDATE", id(seq), x, y, pressure)
        elif et in (Gdk.EventType.TOUCH_END, Gdk.EventType.TOUCH_CANCEL):
            self._end_touch(seq)
            self._log("TOUCH_END", id(seq), x, y, pressure)
            self.queue_draw()
        return True

    def _begin_touch(self, seq, x, y, pressure):
        tid = self.next_touch_id
        self.next_touch_id += 1
        tp = TouchPoint(seq, tid, x, y, pressure)
        self.active[seq] = tp

        # If first two touches start a pinch baseline
        if len(self.active) == 2:
            self.capture_pinch_baseline()

        # Edge coverage mark
        self.mark_edges(x, y)

    def _end_touch(self, seq):
        tp = self.active.pop(seq, None)
        if tp:
            self.dead_trails.append((tp.id, list(tp.trail)))
            # Tap target check: tap = short trail
            if self.tap_mode:
                self.check_tap_hit(tp)

        # Reset pinch baseline when fewer than 2 touches
        if len(self.active) < 2:
            self.pinch_baseline = None
            self.pinch_live = None

    def _log(self, ev, seq_id, x, y, pressure):
        if not self.csv:
            return
        try:
            self.csv.writerow([now_ms(), ev, seq_id, round(x,2), round(y,2), "" if pressure is None else round(pressure,3)])
            self.log_fp.flush()
        except Exception:
            pass

    # ---------- Tests ----------
    def spawn_targets(self):
        self.tap_targets.clear()
        alloc = self.da.get_allocation()
        w, h = alloc.width, alloc.height
        margin = 60
        for _ in range(self.targets_count):
            self.tap_targets.append([random.randint(margin, max(margin, w - margin)),
                                     random.randint(margin, max(margin, h - margin)),
                                     False])  # [x, y, hit]

    def check_tap_hit(self, tp: TouchPoint):
        if not self.tap_targets:
            return
        # If the stroke is short (a tap), consider nearest target
        if len(tp.trail) <= 5:
            endx, endy = tp.x, tp.y
            best = None
            best_d2 = 1e12
            for idx, (tx, ty, hit) in enumerate(self.tap_targets):
                if hit:
                    continue
                d2 = (tx - endx)**2 + (ty - endy)**2
                if d2 < best_d2:
                    best = idx
                    best_d2 = d2
            if best is not None and best_d2 <= (self.target_radius*1.2)**2:
                self.tap_targets[best][2] = True
                self.tap_hits += 1
            else:
                self.tap_misses += 1

    def mark_edges(self, x, y):
        alloc = self.da.get_allocation()
        w, h = alloc.width, alloc.height
        t = max(4, int(self.edge_thickness_ratio * min(w, h)))
        if y <= t:
            self.edge_touched["top"] = True
        if x >= w - t:
            self.edge_touched["right"] = True
        if y >= h - t:
            self.edge_touched["bottom"] = True
        if x <= t:
            self.edge_touched["left"] = True

    def capture_pinch_baseline(self):
        pts = list(self.active.values())
        if len(pts) < 2:
            self.pinch_baseline = None
            return
        a, b = pts[0], pts[1]
        cx = (a.x + b.x) / 2.0
        cy = (a.y + b.y) / 2.0
        dx = b.x - a.x
        dy = b.y - a.y
        dist = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(dy, dx))
        if dist < 1e-3:
            dist = 1.0
        self.pinch_baseline = (cx, cy, dist, ang)

    def compute_pinch_live(self):
        if not self.pinch_baseline or len(self.active) < 2:
            self.pinch_live = None
            return
        a, b = list(self.active.values())[:2]
        dx = b.x - a.x
        dy = b.y - a.y
        dist = max(1e-3, math.hypot(dx, dy))
        ang = math.degrees(math.atan2(dy, dx))
        _, _, base_dist, base_ang = self.pinch_baseline
        scale = dist / base_dist
        # Minimal angle difference
        d_ang = ang - base_ang
        while d_ang > 180: d_ang -= 360
        while d_ang < -180: d_ang += 360
        self.pinch_live = (scale, d_ang)

    # ---------- Drawing ----------
    def on_draw(self, widget, cr: cairo.Context):
        t0 = time.time()

        alloc = self.da.get_allocation()
        w, h = alloc.width, alloc.height

        # Background
        cr.set_source_rgb(0.05, 0.06, 0.08)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        if self.grid_on:
            self.draw_grid(cr, w, h)

        if self.edge_mode:
            self.draw_edges(cr, w, h)

        if self.tap_mode:
            self.draw_targets(cr)

        # Dead trails
        for tid, trail in self.dead_trails[-64:]:
            r, g, b = color_for_id(tid)
            cr.set_source_rgba(r, g, b, 0.25)
            self.path_from_points(cr, trail)
            cr.set_line_width(2.0)
            cr.stroke()

        # Active touches
        for tp in self.active.values():
            r, g, b = color_for_id(tp.id)
            # Trail
            cr.set_source_rgba(r, g, b, 0.9)
            self.path_from_points(cr, tp.trail)
            cr.set_line_width(3.0)
            cr.stroke()
            # Dot
            cr.set_source_rgba(r, g, b, 0.95)
            cr.arc(tp.x, tp.y, 14.0, 0, 2*math.pi)
            cr.fill()

            # Label
            cr.set_source_rgb(0.95, 0.95, 0.95)
            self.draw_text(cr, f"ID {tp.id}", tp.x + 18, tp.y - 18, 12)

        # Pinch HUD
        if self.pinch_hud and len(self.active) >= 2:
            if not self.pinch_baseline:
                self.capture_pinch_baseline()
            self.compute_pinch_live()
            if self.pinch_live:
                scale, deg = self.pinch_live
                self.draw_pinch_hud(cr, w, h, scale, deg)

        # HUD (fps, latency, stats)
        self.draw_hud(cr, w, h)

        # FPS timing
        dt = time.time() - t0
        frame_time_ms = max(1.0, dt*1000.0)
        self.frame_times.append(frame_time_ms)
        if len(self.frame_times) >= 5:
            avg_ms = sum(self.frame_times)/len(self.frame_times)
            self.fps = 1000.0/avg_ms

        return False

    def draw_grid(self, cr, w, h):
        cr.set_source_rgba(1, 1, 1, 0.06)
        spacing = max(40, int(min(w,h)/20))
        cr.set_line_width(1.0)
        for x in range(0, w, spacing):
            cr.move_to(x, 0); cr.line_to(x, h)
        for y in range(0, h, spacing):
            cr.move_to(0, y); cr.line_to(w, y)
        cr.stroke()

    def draw_edges(self, cr, w, h):
        t = max(4, int(self.edge_thickness_ratio * min(w, h)))
        # Fill edges with status color
        def col(done):
            return (0.15, 0.5, 0.2, 0.35) if done else (0.6, 0.15, 0.15, 0.25)
        # top
        r,g,b,a = col(self.edge_touched["top"]); cr.set_source_rgba(r,g,b,a)
        cr.rectangle(0, 0, w, t); cr.fill()
        # right
        r,g,b,a = col(self.edge_touched["right"]); cr.set_source_rgba(r,g,b,a)
        cr.rectangle(w - t, 0, t, h); cr.fill()
        # bottom
        r,g,b,a = col(self.edge_touched["bottom"]); cr.set_source_rgba(r,g,b,a)
        cr.rectangle(0, h - t, w, t); cr.fill()
        # left
        r,g,b,a = col(self.edge_touched["left"]); cr.set_source_rgba(r,g,b,a)
        cr.rectangle(0, 0, t, h); cr.fill()

        cr.set_source_rgb(0.9, 0.9, 0.9)
        self.draw_text(cr, "EDGE COVERAGE: touch all bands", 14, 18, 14)

    def draw_targets(self, cr):
        cr.set_line_width(2.0)
        for tx, ty, hit in self.tap_targets:
            if hit:
                cr.set_source_rgba(0.2, 0.8, 0.3, 0.8)
            else:
                cr.set_source_rgba(0.9, 0.9, 0.9, 0.9)
            cr.arc(tx, ty, self.target_radius, 0, 2*math.pi)
            cr.stroke()
            cr.arc(tx, ty, 4, 0, 2*math.pi)
            cr.fill()

    def draw_pinch_hud(self, cr, w, h, scale, deg):
        msg = f"Pinch: ×{scale:.3f}   Rotate: {deg:+.1f}°"
        cr.set_source_rgba(0.95, 0.95, 0.95, 0.95)
        self.draw_text(cr, msg, 14, h - 18, 14)

    def draw_hud(self, cr, w, h):
        # Background bar
        cr.set_source_rgba(0, 0, 0, 0.25)
        cr.rectangle(0, 0, w, 28)
        cr.fill()

        # Build status line
        mode_bits = []
        if self.grid_on: mode_bits.append("Grid")
        if self.edge_mode: mode_bits.append("Edge")
        if self.tap_mode: mode_bits.append("TapTargets")
        if self.pinch_hud: mode_bits.append("PinchHUD")
        if self.logging_on: mode_bits.append("Logging")

        status = f"Touches: {len(self.active)}   Trails: {len(self.dead_trails)}   " \
                 f"FPS: {self.fps:5.1f}   Lat(ms): {self.avg_latency_ms:4.0f}   " \
                 f"Tap H/M: {self.tap_hits}/{self.tap_misses}   " \
                 f"[{' | '.join(mode_bits) or 'Idle'}]"

        cr.set_source_rgba(0.95, 0.95, 0.95, 0.98)
        self.draw_text(cr, status, 10, 20, 13)

    def draw_text(self, cr, text, x, y, size=13):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        cr.move_to(x, y)
        cr.show_text(text)

    def path_from_points(self, cr, pts):
        it = iter(pts)
        try:
            x0, y0 = next(it)
        except StopIteration:
            return
        cr.move_to(x0, y0)
        for x, y in it:
            cr.line_to(x, y)

    # ---------- Latency sampling ----------
    # GTK gives event.time in milliseconds since an arbitrary starting point,
    # but under Wayland it's not always exposed consistently. We estimate using now_ms on receipt.
    # If your stack exposes event.time, you can subtract properly and feel fancy.

    def record_latency(self, sample_ms):
        self.lat_samples.append(sample_ms)
        if self.lat_samples:
            self.avg_latency_ms = sum(self.lat_samples) / len(self.lat_samples)

def main():
    parser = argparse.ArgumentParser(description="Touch input test on GTK3/Cairo/Wayland")
    parser.add_argument("--fullscreen", action="store_true", help="start in fullscreen")
    parser.add_argument("--log", metavar="CSV", help="log events to CSV path")
    args = parser.parse_args()

    app = TouchTester(args)

    # GDK backend heads-up
    display = Gdk.Display.get_default()
    backend = display.get_name() if Gdk.Display.get_default() else "unknown"
    print("If this crashes on Wayland, check WAYLAND_DISPLAY and XDG_RUNTIME_DIR and your UID. Be a grown-up.")

    Gtk.main()

if __name__ == "__main__":
    main()

