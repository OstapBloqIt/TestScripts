#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import cairo
import threading
import time
import math
import csv
import argparse
from collections import deque

from evdev import InputDevice, categorize, ecodes

# ----------------- Utils -----------------
def now_ms(): return int(time.time() * 1000)

def safe_absinfo(dev, code):
    try:
        ai = dev.absinfo(code)
        if ai:
            return ai.min, ai.max
    except Exception:
        pass
    return None, None

def clamp01(v): return 0.0 if v < 0 else 1.0 if v > 1 else v

def color_for_id(i):
    # deterministic, mildly distinct
    r = ((i * 1103515245 + 12345) & 0xFF) / 255.0
    g = ((i * 962359 + 4242) & 0xFF) / 255.0
    b = ((i * 12582917 + 99991) & 0xFF) / 255.0
    return 0.3 + 0.7*r, 0.3 + 0.7*g, 0.3 + 0.7*b

# ----------------- Data -----------------
class Contact:
    __slots__ = ("key", "slot", "tid", "x_raw", "y_raw", "x_px", "y_px",
                 "pressure", "maj", "min", "trail")
    def __init__(self, key, slot=None, tid=None):
        self.key = key
        self.slot = slot
        self.tid = tid
        self.x_raw = self.y_raw = 0
        self.x_px = self.y_px = 0
        self.pressure = None
        self.maj = None
        self.min = None
        self.trail = deque(maxlen=1024)

# ----------------- Reader Thread -----------------
class EvdevReader(threading.Thread):
    def __init__(self, app, devpath, grab=False):
        super().__init__(daemon=True)
        self.app = app
        self.devpath = devpath
        self.grab = grab
        self.stop_flag = threading.Event()
        self.dev = None
        self.has_slots = False
        self.ax_min = self.ax_max = None
        self.ay_min = self.ay_max = None
        self.mx_min = self.mx_max = None
        self.my_min = self.my_max = None
        self.p_min = self.p_max = None
        self.current_slot = 0
        self.proto = "unknown"

    def open(self):
        self.dev = InputDevice(self.devpath)
        if self.grab:
            try: self.dev.grab()
            except Exception: pass

        # Axis info
        self.mx_min, self.mx_max = safe_absinfo(self.dev, ecodes.ABS_MT_POSITION_X)
        self.my_min, self.my_max = safe_absinfo(self.dev, ecodes.ABS_MT_POSITION_Y)
        self.ax_min, self.ax_max = safe_absinfo(self.dev, ecodes.ABS_X)
        self.ay_min, self.ay_max = safe_absinfo(self.dev, ecodes.ABS_Y)
        self.p_min, self.p_max   = safe_absinfo(self.dev, ecodes.ABS_MT_PRESSURE)

        # Protocol detection
        caps = set(c for c, _ in self.dev.capabilities().get(ecodes.EV_ABS, [])) \
               if isinstance(self.dev.capabilities().get(ecodes.EV_ABS, []), list) else set()
        # More robust: just ask the device
        try:
            self.has_slots = self.dev.absinfo(ecodes.ABS_MT_SLOT) is not None
        except Exception:
            self.has_slots = False
        self.proto = "B (slots)" if self.has_slots else "A (legacy)"

        # publish device meta
        GLib.idle_add(self.app.set_device_meta,
                      self.dev.name, self.dev.path, self.proto,
                      (self.mx_min, self.mx_max, self.my_min, self.my_max),
                      (self.ax_min, self.ax_max, self.ay_min, self.ay_max),
                      priority=GLib.PRIORITY_DEFAULT)

    def scale_xy(self, x_raw, y_raw):
        # choose MT ranges if present, else single-touch
        x0,x1 = (self.mx_min, self.mx_max) if self.mx_min is not None else (self.ax_min, self.ax_max)
        y0,y1 = (self.my_min, self.my_max) if self.my_min is not None else (self.ay_min, self.ay_max)
        w, h = self.app.get_canvas_size()
        if x0 is None or y0 is None or x1 == x0 or y1 == y0 or w <= 0 or h <= 0:
            return float(x_raw), float(y_raw)
        # normalize
        nx = (x_raw - x0) / (x1 - x0)
        ny = (y_raw - y0) / (y1 - y0)
       # First: physical rotation mapping
        rot = getattr(self.app, "rotate", "0")
        if rot == "90cw":
            rx, ry = ny, 1.0 - nx
        elif rot == "90ccw":
            rx, ry = 1.0 - ny, nx
        elif rot == "180":
            rx, ry = 1.0 - nx, 1.0 - ny
        else:
            rx, ry = nx, ny

        # Then: user toggles
        if self.app.swap_xy:
            rx, ry = ry, rx
        if self.app.inv_x:
            rx = 1.0 - rx
        if self.app.inv_y:
            ry = 1.0 - ry

        return rx * w, ry * h
    
    def stop(self):
        self.stop_flag.set()
        try:
            if self.dev and self.grab:
                self.dev.ungrab()
        except Exception:
            pass

    def run(self):
        self.open()
        # Working sets for Protocol A aggregation
        a_contact = None  # temp store for Protocol A between SYN_MT_REPORTs
        last_report_ms = now_ms()

        for ev in self.dev.read_loop():
            if self.stop_flag.is_set():
                break

            # FPS-ish latency sampling
            if ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT:
                now = now_ms()
                self.app.record_input_heartbeat(now - last_report_ms)
                last_report_ms = now
                continue

            if ev.type != ecodes.EV_ABS and ev.type != ecodes.EV_KEY:
                continue

            if self.has_slots:
                # -------- Protocol B ----------
                if ev.type == ecodes.EV_ABS:
                    if ev.code == ecodes.ABS_MT_SLOT:
                        self.current_slot = ev.value
                    elif ev.code == ecodes.ABS_MT_TRACKING_ID:
                        if ev.value == -1:
                            # liftoff
                            GLib.idle_add(self.app.liftoff_slot, self.current_slot)
                        else:
                            GLib.idle_add(self.app.ensure_slot, self.current_slot, ev.value)
                            GLib.idle_add(self.app.log_csv, "TRACK", self.current_slot, None, None, None, None, None, None, (None, None))
                    elif ev.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_MT_POSITION_Y,
                                     ecodes.ABS_MT_PRESSURE, ecodes.ABS_MT_TOUCH_MAJOR, ecodes.ABS_MT_TOUCH_MINOR):
                        # fetch contact to update
                        code = ev.code
                        val  = ev.value
                        # read pos pair if we have it
                        if code == ecodes.ABS_MT_POSITION_X:
                            x_raw = val
                            y_raw = None
                        elif code == ecodes.ABS_MT_POSITION_Y:
                            x_raw = None
                            y_raw = val
                        else:
                            x_raw = y_raw = None

                        GLib.idle_add(self.app.update_slot_abs,
                                      self.current_slot, code, val, x_raw, y_raw, self.scale_xy,
                                      priority=GLib.PRIORITY_DEFAULT)
                elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                    GLib.idle_add(self.app.note_btn_touch, int(ev.value))
            else:
                # -------- Protocol A ----------
                if ev.type == ecodes.EV_ABS:
                    if ev.code == ecodes.ABS_MT_TRACKING_ID:
                        tid = ev.value
                        if tid == -1:
                            # end last temp contact
                            GLib.idle_add(self.app.liftoff_tid_latest)
                            a_contact = None
                        else:
                            GLib.idle_add(self.app.ensure_tid, tid)
                            a_contact = tid
                            GLib.idle_add(self.app.log_csv, "TRACK", None, tid, None, None, None, None, None, (None, None))
                    elif ev.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_MT_POSITION_Y,
                                     ecodes.ABS_MT_PRESSURE, ecodes.ABS_MT_TOUCH_MAJOR, ecodes.ABS_MT_TOUCH_MINOR):
                        GLib.idle_add(self.app.update_tid_abs,
                                      a_contact, ev.code, ev.value, self.scale_xy)
                    elif ev.code in (ecodes.ABS_X, ecodes.ABS_Y):
                        # single-touch fallback devices
                        GLib.idle_add(self.app.update_single_abs,
                                      ev.code, ev.value, self.scale_xy)
                elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                    GLib.idle_add(self.app.note_btn_touch, int(ev.value))

# ----------------- GTK App -----------------
class EvdevTouchApp(Gtk.Window):
    def __init__(self, args):
        super().__init__(title="evdev Touch Tester")
        self.set_default_size(1024, 600)
        self.connect("delete-event", self.on_quit)

        # flags
        if args.fullscreen: self.fullscreen()
        self.grid_on = True
        self.logging_on = bool(args.log)
        self.swap_xy = args.swap_xy
        self.inv_x = args.invert_x
        self.inv_y = args.invert_y
        self.rotate = args.rotate


        # device meta
        self.dev_name = "unknown"
        self.dev_path = args.device
        self.proto    = "unknown"
        self.mt_range = (None, None, None, None)
        self.st_range = (None, None, None, None)

        # contacts
        self.contacts = {}   # key -> Contact (key is "S<slot>" or "T<tid>" or "single")
        self.dead_trails = deque(maxlen=64)
        self.latest_tid = None

        # drawing/fps
        self.frame_times = deque(maxlen=120)
        self.fps = 0.0
        self.input_heartbeat_ms = 0

        # CSV
        self.log_path = args.log
        self.csv = None
        self.log_fp = None
        if self.logging_on: self.open_log()

        # UI
        self.da = Gtk.DrawingArea()
        self.da.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.da.set_can_focus(True)
        self.add(self.da)
        self.da.connect("draw", self.on_draw)
        self.connect("key-press-event", self.on_key)

        GLib.timeout_add(16, self.on_tick)
        self.show_all()
        self.da.grab_focus()

        # reader
        self.reader = EvdevReader(self, args.device, grab=args.grab)
        self.reader.start()

    # ---- device meta ----
    def set_device_meta(self, name, path, proto, mt_range, st_range):
        self.dev_name = name
        self.dev_path = path
        self.proto    = proto
        self.mt_range = mt_range
        self.st_range = st_range
        return False

    # ---- csv ----
    def open_log(self):
        try:
            self.log_fp = open(self.log_path, "w", newline="")
            self.csv = csv.writer(self.log_fp)
            self.csv.writerow(["ts_ms","ev","slot","tid","x_raw","y_raw","x_px","y_px","pressure","maj","min"])
        except Exception as e:
            print("CSV open failed:", e)
            self.csv = None

    def log_csv(self, ev, slot, tid, x_raw, y_raw, x_px, y_px, p, maj_min=None):
        if not self.csv: return False
        maj, mmin = (maj_min if isinstance(maj_min, tuple) else (None,None))
        self.csv.writerow([now_ms(), ev, slot, tid, x_raw, y_raw,
                           None if x_px is None else round(x_px,2),
                           None if y_px is None else round(y_px,2),
                           p, maj, mmin])
        try: self.log_fp.flush()
        except Exception: pass
        return False

    # ---- helpers ----
    def get_canvas_size(self):
        alloc = self.da.get_allocation()
        return alloc.width, alloc.height

    def note_btn_touch(self, v):  # 0/1
        # doesn’t draw, just logged
        self.log_csv("BTN_TOUCH", None, None, None, None, None, None, v, None)
        return False

    # Protocol B updaters
    def ensure_slot(self, slot, tid):
        key = f"S{slot}"
        c = self.contacts.get(key)
        if c is None:
            c = Contact(key, slot=slot, tid=tid)
            self.contacts[key] = c
        else:
            c.tid = tid
        return False

    def liftoff_slot(self, slot):
        key = f"S{slot}"
        c = self.contacts.pop(key, None)
        if c and len(c.trail) > 1:
            self.dead_trails.append((c.key, list(c.trail)))
            self.log_csv("UP", slot, c.tid, c.x_raw, c.y_raw, c.x_px, c.y_px, c.pressure, (c.maj, c.min))
        return False

    def update_slot_abs(self, slot, code, val, x_raw, y_raw, scaler):
        key = f"S{slot}"
        c = self.contacts.get(key)
        if c is None:
            c = Contact(key, slot=slot)
            self.contacts[key] = c
        changed = False
        if code == ecodes.ABS_MT_POSITION_X:
            c.x_raw = val; changed = True
        elif code == ecodes.ABS_MT_POSITION_Y:
            c.y_raw = val; changed = True
        elif code == ecodes.ABS_MT_PRESSURE:
            c.pressure = val
        elif code == ecodes.ABS_MT_TOUCH_MAJOR:
            c.maj = val
        elif code == ecodes.ABS_MT_TOUCH_MINOR:
            c.min = val

        if changed:
            c.x_px, c.y_px = scaler(c.x_raw, c.y_raw)
            c.trail.append((c.x_px, c.y_px))
            self.log_csv("MOVE", slot, c.tid, c.x_raw, c.y_raw, c.x_px, c.y_px, c.pressure, (c.maj, c.min))
        return False

    # Protocol A updaters
    def ensure_tid(self, tid):
        key = f"T{tid}"
        self.latest_tid = tid
        if key not in self.contacts:
            self.contacts[key] = Contact(key, tid=tid)
        return False

    def liftoff_tid_latest(self):
        if self.latest_tid is None: return False
        key = f"T{self.latest_tid}"
        c = self.contacts.pop(key, None)
        if c and len(c.trail) > 1:
            self.dead_trails.append((c.key, list(c.trail)))
            self.log_csv("UP", None, c.tid, c.x_raw, c.y_raw, c.x_px, c.y_px, c.pressure, (c.maj, c.min))
        self.latest_tid = None
        return False

    def update_tid_abs(self, tid, code, val, scaler):
        if tid is None:  # no tracking id yet, ignore
            return False
        key = f"T{tid}"
        c = self.contacts.get(key)
        if c is None:
            c = Contact(key, tid=tid)
            self.contacts[key] = c
        changed = False
        if code == ecodes.ABS_MT_POSITION_X:
            c.x_raw = val; changed = True
        elif code == ecodes.ABS_MT_POSITION_Y:
            c.y_raw = val; changed = True
        elif code == ecodes.ABS_MT_PRESSURE:
            c.pressure = val
        elif code == ecodes.ABS_MT_TOUCH_MAJOR:
            c.maj = val
        elif code == ecodes.ABS_MT_TOUCH_MINOR:
            c.min = val

        if changed:
            c.x_px, c.y_px = scaler(c.x_raw, c.y_raw)
            c.trail.append((c.x_px, c.y_px))
            self.log_csv("MOVE", None, c.tid, c.x_raw, c.y_raw, c.x_px, c.y_px, c.pressure, (c.maj, c.min))
        return False

    # Single-touch fallback (ABS_X/Y)
    def update_single_abs(self, code, val, scaler):
        key = "single"
        c = self.contacts.get(key)
        if c is None:
            c = Contact(key)
            self.contacts[key] = c
        if code == ecodes.ABS_X:
            c.x_raw = val
        elif code == ecodes.ABS_Y:
            c.y_raw = val
        c.x_px, c.y_px = scaler(c.x_raw, c.y_raw)
        c.trail.append((c.x_px, c.y_px))
        self.log_csv("MOVE", None, None, c.x_raw, c.y_raw, c.x_px, c.y_px, None, (None, None))
        return False

    # ---- timing ----
    def record_input_heartbeat(self, dt_ms):
        # crude "input cadence" number, not end-to-end latency
        self.input_heartbeat_ms = dt_ms

    # ---- drawing ----
    def on_tick(self):
        self.queue_draw()
        return True

    def on_draw(self, widget, cr: cairo.Context):
        t0 = time.time()
        w, h = self.get_canvas_size()

        # bg
        cr.set_source_rgb(0.05, 0.06, 0.08)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        if self.grid_on:
            cr.set_source_rgba(1,1,1,0.06)
            step = max(40, int(min(w,h)/20))
            cr.set_line_width(1.0)
            for x in range(0, w, step):
                cr.move_to(x, 0); cr.line_to(x, h)
            for y in range(0, h, step):
                cr.move_to(0, y); cr.line_to(w, y)
            cr.stroke()

        # dead trails
        for key, trail in self.dead_trails:
            ident = hash(key) & 0xFFFF
            r,g,b = color_for_id(ident)
            cr.set_source_rgba(r, g, b, 0.25)
            self.path_from_points(cr, trail)
            cr.set_line_width(2.0)
            cr.stroke()

        # live contacts
        for key, c in self.contacts.items():
            ident = hash(key) & 0xFFFF
            r,g,b = color_for_id(ident)
            cr.set_source_rgba(r, g, b, 0.9)
            self.path_from_points(cr, c.trail)
            cr.set_line_width(3.0)
            cr.stroke()

            # dot size by pressure/size
            radius = 12.0
            if c.pressure is not None:
                radius = 8.0 + 12.0 * clamp01(float(c.pressure) / 1023.0)
            elif c.maj is not None:
                radius = 6.0 + 0.4 * c.maj
            cr.set_source_rgba(r, g, b, 0.95)
            cr.arc(c.x_px, c.y_px, radius, 0, 2*math.pi)
            cr.fill()

            # label
            cr.set_source_rgb(0.95,0.95,0.95)
            self.text(cr, f"{key}", c.x_px + 16, c.y_px - 16, 12)

        # HUD
        self.draw_hud(cr, w, h)

        # fps
        dt = (time.time() - t0) * 1000.0
        self.frame_times.append(max(1.0, dt))
        if len(self.frame_times) >= 5:
            avg = sum(self.frame_times)/len(self.frame_times)
            self.fps = 1000.0/avg
        return False

    def path_from_points(self, cr, pts):
        it = iter(pts)
        try: x0, y0 = next(it)
        except StopIteration: return
        cr.move_to(x0, y0)
        for x, y in it:
            cr.line_to(x, y)

    def text(self, cr, s, x, y, size=13):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        cr.move_to(x, y)
        cr.show_text(s)

    def text_ellipsized(self, cr, s, x, y, size, max_w):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        # Fits already?
        if cr.text_extents(s).width <= max_w:
            cr.move_to(x, y); cr.show_text(s); return
        # Binary search the longest prefix that fits
        lo, hi = 0, len(s)
        ell = "…"
        while lo < hi:
            mid = (lo + hi) // 2
            if cr.text_extents(s[:mid] + ell).width <= max_w:
                lo = mid + 1
            else:
                hi = mid
        s = s[:max(0, hi - 1)] + ell
        cr.move_to(x, y); cr.show_text(s)

    def draw_hud(self, cr, w, h):
        cr.set_source_rgba(0,0,0,0.28)
        cr.rectangle(0, 0, w, 30)
        cr.fill()
        r = self.mt_range; s = self.st_range
        modes = []
        if self.grid_on: modes.append("Grid")
        if self.logging_on: modes.append("Logging")
        if self.swap_xy: modes.append("SwapXY")
        if self.inv_x: modes.append("InvX")
        if self.inv_y: modes.append("InvY")
        msg = (f"{self.dev_name} [{self.dev_path}]  Proto:{self.proto}  "
               f"MT X[{r[0]},{r[1]}] Y[{r[2]},{r[3]}] | "
               f"ST X[{s[0]},{s[1]}] Y[{s[2]},{s[3]}]  "
               f"Contacts:{len(self.contacts)}  FPS:{self.fps:4.1f}  "
               f"InCad:{self.input_heartbeat_ms:>3}ms  "
               f"[{', '.join(modes) or 'Idle'}]")
        cr.set_source_rgba(0.95,0.95,0.95,0.98)
        # clamp to width with 8px padding
        self.text_ellipsized(cr, msg, 8, 20, 13, w - 16)

    # ---- keys / lifecycle ----
    def on_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "Escape": self.on_quit(None, None); return True
        if key in ("f","F"):
            if self.get_window().get_state() & Gdk.WindowState.FULLSCREEN: self.unfullscreen()
            else: self.fullscreen(); return True
        if key in ("g","G"): self.grid_on = not self.grid_on; return True
        if key in ("l","L"):
            self.logging_on = not self.logging_on
            if self.logging_on and not self.csv: self.open_log()
            return True
        if key in ("c","C"):
            self.contacts.clear(); self.dead_trails.clear()
            return True
        if key in ("x","X"): self.swap_xy = not self.swap_xy; return True
        if key in ("i","I"): self.inv_x = not self.inv_x; return True
        if key in ("k","K"): self.inv_y = not self.inv_y; return True
        return False

    def on_quit(self, *_):
        try: self.reader.stop()
        except Exception: pass
        try:
            if self.csv: self.log_fp.close()
        except Exception: pass
        Gtk.main_quit()
        return True

# ----------------- main -----------------
def main():
    ap = argparse.ArgumentParser(description="Raw evdev touchscreen visual tester")
    ap.add_argument("--device", required=True, help="path like /dev/input/event2")
    ap.add_argument("--grab", action="store_true", help="exclusive grab device")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--log", help="CSV output path")
    ap.add_argument("--swap-xy", action="store_true", help="swap X and Y axes")
    ap.add_argument("--invert-x", action="store_true", dest="invert_x")
    ap.add_argument("--invert-y", action="store_true", dest="invert_y")
    ap.add_argument("--rotate", choices=["0", "90cw", "90ccw", "180"], default="0",
                help="apply screen rotation to raw touch mapping")
    args = ap.parse_args()

    app = EvdevTouchApp(args)
    Gtk.main()

if __name__ == "__main__":
    main()

