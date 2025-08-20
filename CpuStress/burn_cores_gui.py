#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Wayland/Weston CPU burner + live monitor (GTK3 + Cairo).
# - Spawns one burn worker per visible CPU (respecting cgroups/affinity).
# - Renders per-CPU usage bars, temperatures, frequencies, and load averages.
# - Works inside containers if GTK/Wayland/cairo are present.
#
# Controls:
#   Esc / q   : quit
#   Space     : toggle burn on/off
#   +/-       : change worker count (when burning)
#   f         : toggle fullscreen
#
# Example:
#   XDG_RUNTIME_DIR=/tmp/1000-runtime-dir WAYLAND_DISPLAY=wayland-0 \
#   python3 burn_cores_gui.py --fullscreen --interval 0.3
#
# Notes:
# - CPU usage from /proc/stat
# - Temps from /sys/class/thermal/thermal_zone*/temp
# - Frequencies from /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq

import argparse
import math
import os
import signal
import sys
import time
from glob import glob
from multiprocessing import Process, Event

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

try:
    import cairo
except ImportError:
    # Some images package cairo under gi.repository; try that as a fallback.
    from gi.repository import cairo  # type: ignore

# --------------------- Data collectors ---------------------

class CpuStatReader:
    def __init__(self):
        self.prev = {}

    @staticmethod
    def _read_proc_stat():
        lines = []
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu") and line[3:4].isdigit():
                    lines.append(line.strip())
        return lines

    def usage_per_cpu(self):
        lines = self._read_proc_stat()
        usages = []
        for line in lines:
            parts = line.split()
            cpu = parts[0]  # e.g., cpu0
            nums = list(map(int, parts[1:]))  # user nice system idle iowait irq softirq steal guest guest_nice
            if len(nums) < 4:
                continue
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
            total = sum(nums)
            ptotal, pidle = self.prev.get(cpu, (total, idle))
            dt = max(1, total - ptotal)
            didle = max(0, idle - pidle)
            busy = max(0.0, 1.0 - (didle / dt))
            usages.append(busy)
            self.prev[cpu] = (total, idle)
        return usages  # list of floats 0..1

def online_cpus():
    try:
        return sorted(os.sched_getaffinity(0))
    except Exception:
        cnt = os.cpu_count() or 1
        return list(range(cnt))

def cpu_freq_paths():
    paths = []
    for cdir in sorted(glob("/sys/devices/system/cpu/cpu[0-9]*")):
        f = os.path.join(cdir, "cpufreq", "scaling_cur_freq")
        if os.path.exists(f):
            paths.append(f)
    return paths

def read_freq_khz(path):
    try:
        return int(open(path, "r").read().strip())
    except Exception:
        return None

def find_thermal_sensors():
    sensors = []
    for tz in sorted(glob("/sys/class/thermal/thermal_zone*")):
        ttype_path = os.path.join(tz, "type")
        ttemp_path = os.path.join(tz, "temp")
        try:
            tname = open(ttype_path, "r").read().strip()
        except Exception:
            continue
        if not os.path.exists(ttemp_path):
            continue
        lname = tname.lower()
        # Prefer CPU/SOC-ish zones but show everything if nothing matches
        sensors.append((tname, ttemp_path, ("cpu" in lname) or ("soc" in lname)))
    # If we found any "preferred", filter to those; else keep all
    if any(p for _, _, p in sensors):
        sensors = [(n, p) for n, p, pref in sensors if pref]
    else:
        sensors = [(n, p) for n, p, _ in sensors]
    return sensors

def read_temp_mC(path):
    try:
        return int(open(path, "r").read().strip())
    except Exception:
        return None

# --------------------- Burner ---------------------

def set_affinity(cpu_id):
    try:
        os.sched_setaffinity(0, {cpu_id})
    except Exception:
        pass

def burn_loop(stop_evt: Event, cpu_id: int, no_affinity: bool):
    if not no_affinity:
        set_affinity(cpu_id)
    x = 1.0001
    y = 123456789
    while not stop_evt.is_set():
        x = x * 1.0000003 + math.sqrt(x) - math.log(x)
        y = (y * 1664525 + 1013904223) & 0xFFFFFFFF
        if (y & 0xFF) == 0:
            x = x % 1000.0
        if x < 0:
            break

class BurnerManager:
    def __init__(self, no_affinity=False):
        self.stop_evt = Event()
        self.procs = []
        self.no_affinity = no_affinity
        self.cpus = online_cpus()

    def active_workers(self):
        return sum(1 for p in self.procs if p.is_alive())

    def start(self, nworkers: int):
        self.stop_evt.clear()
        # Cap to visible CPUs
        n = max(0, min(nworkers, len(self.cpus)))
        # Spawn additional if needed
        while self.active_workers() < n:
            idx = self.active_workers()
            target_cpu = self.cpus[idx % len(self.cpus)]
            p = Process(target=burn_loop, args=(self.stop_evt, target_cpu, self.no_affinity), daemon=False)
            p.start()
            self.procs.append(p)
        # If too many, stop extras
        while self.active_workers() > n:
            self.stop_evt.set()
            self.join_all(timeout=0.5)
            self.stop_evt.clear()
            # Relaunch exactly n
            self.stop_all()
            self.procs = []
            for i in range(n):
                target_cpu = self.cpus[i % len(self.cpus)]
                p = Process(target=burn_loop, args=(self.stop_evt, target_cpu, self.no_affinity), daemon=False)
                p.start()
                self.procs.append(p)

    def stop_all(self):
        self.stop_evt.set()
        self.join_all(timeout=2.0)

    def join_all(self, timeout=2.0):
        t0 = time.time()
        for p in self.procs:
            if p.is_alive():
                p.join(timeout=max(0.0, timeout - (time.time() - t0)))

# --------------------- UI ---------------------

class MonitorUI(Gtk.Window):
    def __init__(self, interval, start_burners, initial_workers, no_affinity):
        super().__init__(title="i.MX8M Mini CPU Monitor")
        self.set_app_paintable(True)
        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)

        self.da = Gtk.DrawingArea()
        self.da.connect("draw", self.on_draw)
        self.add(self.da)

        self.interval = max(0.1, float(interval))
        self.reader = CpuStatReader()
        self.freq_paths = cpu_freq_paths()
        self.sensors = find_thermal_sensors()
        self.last_usages = []
        self.last_freqs = []
        self.last_temps = []
        self.last_load = (0.0, 0.0, 0.0)

        self.fullscreened = False

        self.burner = BurnerManager(no_affinity=no_affinity)
        self.burning = bool(start_burners)
        self.target_workers = initial_workers if initial_workers > 0 else len(online_cpus())
        if self.burning:
            self.burner.start(self.target_workers)

        GLib.timeout_add(int(self.interval * 1000), self.tick)

    # ------------- events -------------
    def on_destroy(self, *_):
        try:
            self.burner.stop_all()
        except Exception:
            pass
        Gtk.main_quit()

    def on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval).lower()
        if key in ("escape", "q"):
            self.destroy()
            return True
        if key == "space":
            self.burning = not self.burning
            if self.burning:
                self.burner.start(self.target_workers)
            else:
                self.burner.stop_all()
            self.queue_draw()
            return True
        if key in ("plus", "kp_add"):
            if self.burning:
                self.target_workers = min(self.target_workers + 1, len(online_cpus()))
                self.burner.start(self.target_workers)
                self.queue_draw()
            return True
        if key in ("minus", "kp_subtract"):
            if self.burning:
                self.target_workers = max(self.target_workers - 1, 0)
                self.burner.start(self.target_workers)
                self.queue_draw()
            return True
        if key == "f":
            if self.fullscreened:
                self.unfullscreen()
            else:
                self.fullscreen()
            self.fullscreened = not self.fullscreened
            return True
        return False

    # ------------- update -------------
    def tick(self):
        try:
            self.last_usages = self.reader.usage_per_cpu()
            self.last_freqs = [read_freq_khz(p) for p in self.freq_paths] if self.freq_paths else []
            try:
                self.last_load = os.getloadavg()
            except Exception:
                self.last_load = (0.0, 0.0, 0.0)
            self.last_temps = [read_temp_mC(p) for _, p in self.sensors] if self.sensors else []
        except Exception:
            pass
        self.queue_draw()
        return True

    # ------------- drawing helpers -------------
    @staticmethod
    def _draw_text(cr, x, y, txt, size=16, align="left"):
        cr.save()
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        xbearing, ybearing, w, h, xa, ya = cr.text_extents(txt)
        if align == "left":
            tx = x
        elif align == "center":
            tx = x - w / 2
        else:
            tx = x - w
        cr.move_to(tx, y + h)
        cr.show_text(txt)
        cr.restore()

    @staticmethod
    def _hsv_to_rgb(h, s, v):
        # quick-and-dirty HSV to RGB for heatmap
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - f * s)
        t = v * (1.0 - (1.0 - f) * s)
        i = i % 6
        if i == 0: r, g, b = v, t, p
        elif i == 1: r, g, b = q, v, p
        elif i == 2: r, g, b = p, v, t
        elif i == 3: r, g, b = p, q, v
        elif i == 4: r, g, b = t, p, v
        else: r, g, b = v, p, q
        return r, g, b

    # ------------- draw -------------
    def on_draw(self, _widget, cr):
        w = self.get_allocated_width()
        h = self.get_allocated_height()

        # Background
        cr.set_source_rgb(0.08, 0.09, 0.11)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        pad = 20
        x = pad
        y = pad

        # Header
        cr.set_source_rgb(0.9, 0.9, 0.9)
        title = "i.MX8M Mini Thermal/Load Monitor"
        self._draw_text(cr, x, y, title, size=22, align="left")
        y += 30

        # Load averages + status line
        la = self.last_load
        status = f"Load avg: {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}    Burn: {'ON' if self.burning else 'OFF'}  Workers: {self.burner.active_workers()}/{len(online_cpus())}"
        cr.set_source_rgb(0.75, 0.75, 0.75)
        self._draw_text(cr, x, y, status, size=16, align="left")
        y += 24

        # Per-CPU bars
        usages = self.last_usages
        n = len(usages)
        if n > 0:
            bar_h = max(22, int((h - y - 200) / max(4, n)))
            bar_h = min(bar_h, 40)
            bar_w = w - 2 * pad
            for i, u in enumerate(usages):
                uy = y + i * (bar_h + 6)
                # bar background
                cr.set_source_rgb(0.18, 0.19, 0.22)
                cr.rectangle(x, uy, bar_w, bar_h)
                cr.fill()
                # bar fill with heat color
                hue = max(0.0, min(0.33 * (1.0 - u), 0.33))  # green->red
                r, g, b = self._hsv_to_rgb(hue, 0.9, 0.95)
                cr.set_source_rgb(r, g, b)
                cr.rectangle(x, uy, int(bar_w * u), bar_h)
                cr.fill()
                # label
                cr.set_source_rgb(0.95, 0.95, 0.95)
                percent = int(u * 100)
                label = f"CPU{i}: {percent:3d}%"
                # freq if available
                if i < len(self.last_freqs) and self.last_freqs[i]:
                    label += f"  {self.last_freqs[i]//1000} MHz"
                self._draw_text(cr, x + 6, uy + 3, label, size=14, align="left")

            y += n * (bar_h + 6) + 10

        # Temperatures
        temps = self.last_temps
        if self.sensors:
            cr.set_source_rgb(0.9, 0.9, 0.9)
            self._draw_text(cr, x, y, "Thermal sensors:", size=18, align="left")
            y += 26
            box_w = (w - 2 * pad)
            col_w = max(220, box_w // max(1, min(len(self.sensors), 3)))
            for idx, (name, _) in enumerate(self.sensors):
                px = x + (idx % (box_w // col_w)) * col_w
                py = y + (idx // (box_w // col_w)) * 56
                t_mC = temps[idx] if idx < len(temps) else None
                label = name
                if t_mC is not None:
                    tC = t_mC / 1000.0
                    label += f": {tC:.1f}°C"
                    # temp bar with 40..100 C mapping
                    tnorm = (tC - 40.0) / 60.0
                    tnorm = 0.0 if tnorm < 0 else 1.0 if tnorm > 1 else tnorm
                    hue = max(0.0, min(0.33 * (1.0 - tnorm), 0.33))
                    r, g, b = self._hsv_to_rgb(hue, 0.95, 0.95)
                    cr.set_source_rgb(0.18, 0.19, 0.22)
                    cr.rectangle(px, py + 6, col_w - 20, 18)
                    cr.fill()
                    cr.set_source_rgb(r, g, b)
                    cr.rectangle(px, py + 6, (col_w - 20) * tnorm, 18)
                    cr.fill()
                cr.set_source_rgb(0.85, 0.85, 0.85)
                self._draw_text(cr, px, py - 2, label, size=14, align="left")
            y += 80

        # Footer
        cr.set_source_rgb(0.6, 0.6, 0.65)
        footer = "Space: toggle burn   +/-: workers   f: fullscreen   Esc/q: quit"
        self._draw_text(cr, w - pad, h - pad - 18, footer, size=14, align="right")

        return False

# --------------------- main ---------------------

def main():
    ap = argparse.ArgumentParser(description="CPU burner + Wayland/GTK monitor")
    ap.add_argument("--fullscreen", action="store_true", help="Start fullscreen")
    ap.add_argument("--interval", type=float, default=0.5, help="UI update interval seconds")
    ap.add_argument("--start-burn", action="store_true", help="Start with burners ON")
    ap.add_argument("--workers", type=int, default=0, help="Initial workers (0=one per visible CPU)")
    ap.add_argument("--no-affinity", action="store_true", help="Do not pin workers to specific CPUs")
    args = ap.parse_args()

    win = MonitorUI(interval=args.interval,
                    start_burners=args.start_burn,
                    initial_workers=(args.workers if args.workers > 0 else len(online_cpus())),
                    no_affinity=args.no_affinity)
    win.set_default_size(800, 1280)  # sane default for rotated 1280x800 panel
    if args.fullscreen:
        win.fullscreen()
        win.fullscreened = True
    win.show_all()
    # Graceful exit on SIGTERM
    def handle_sig(_s, _f):
        try:
            win.destroy()
        except Exception:
            Gtk.main_quit()
    signal.signal(signal.SIGTERM, handle_sig)
    Gtk.main()

if __name__ == "__main__":
    main()
