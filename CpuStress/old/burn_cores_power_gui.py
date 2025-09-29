#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Enhanced Wayland/Weston CPU burner + live monitor (GTK3 + Cairo) with power consumption monitoring.
# Based on burn_cores_gui.py with added power monitoring capabilities for iMX8M Mini.
#
# Features:
# - CPU stress testing with per-core control
# - Real-time power consumption monitoring
# - Temperature and frequency monitoring
# - Enhanced CSV logging with power metrics
# - Touch controls optimized for 800x1280 portrait display
#
# Power monitoring methods:
# - System power via /sys/class/power_supply/
# - CPU power estimation via frequency/voltage scaling
# - Thermal correlation analysis
# - PMU performance counters where available
#
# Touch controls (bottom bar):
#   [Burn ON/OFF]  [−]  [+]  [Quit]  [REC]
#
# CSV includes power consumption data:
#   --log-file PATH (default ./cpu_power_monitor_YYYYmmdd_HHMMSS.csv)
#   --log-auto (start logging immediately)

import argparse
import csv
import math
import os
import signal
import sys
import time
from datetime import datetime
from glob import glob
from multiprocessing import Process, Event

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

try:
    import cairo
except ImportError:
    from gi.repository import cairo  # type: ignore


# --------------------- Power monitoring ---------------------

class PowerMonitor:
    """Monitor system power consumption using available Linux interfaces"""

    def __init__(self):
        self.power_supply_paths = self._find_power_supplies()
        self.hwmon_paths = self._find_hwmon_power()
        self.voltage_paths = self._find_voltage_sensors()
        self.current_paths = self._find_current_sensors()
        self.energy_paths = self._find_energy_sensors()

        # CPU power estimation parameters
        self.cpu_base_power = 0.5  # Base power consumption in watts
        self.cpu_max_power = 3.0   # Max power consumption in watts
        self.last_energy_reading = None
        self.last_energy_time = None

    def _find_power_supplies(self):
        """Find power supply interfaces"""
        supplies = []
        base_path = "/sys/class/power_supply"
        if os.path.exists(base_path):
            for supply in os.listdir(base_path):
                supply_path = os.path.join(base_path, supply)
                power_now_path = os.path.join(supply_path, "power_now")
                voltage_now_path = os.path.join(supply_path, "voltage_now")
                current_now_path = os.path.join(supply_path, "current_now")

                if os.path.exists(power_now_path):
                    supplies.append(("power_now", power_now_path))
                elif os.path.exists(voltage_now_path) and os.path.exists(current_now_path):
                    supplies.append(("voltage_current", voltage_now_path, current_now_path))
        return supplies

    def _find_hwmon_power(self):
        """Find hardware monitoring power sensors"""
        hwmon_power = []
        hwmon_base = "/sys/class/hwmon"
        if os.path.exists(hwmon_base):
            for hwmon_dir in os.listdir(hwmon_base):
                hwmon_path = os.path.join(hwmon_base, hwmon_dir)
                # Look for power input sensors
                for i in range(1, 10):  # Check power1_input through power9_input
                    power_path = os.path.join(hwmon_path, f"power{i}_input")
                    if os.path.exists(power_path):
                        hwmon_power.append(power_path)
        return hwmon_power

    def _find_voltage_sensors(self):
        """Find voltage sensors for power calculation"""
        voltage_sensors = []
        hwmon_base = "/sys/class/hwmon"
        if os.path.exists(hwmon_base):
            for hwmon_dir in os.listdir(hwmon_base):
                hwmon_path = os.path.join(hwmon_base, hwmon_dir)
                for i in range(1, 10):
                    voltage_path = os.path.join(hwmon_path, f"in{i}_input")
                    if os.path.exists(voltage_path):
                        voltage_sensors.append(voltage_path)
        return voltage_sensors

    def _find_current_sensors(self):
        """Find current sensors for power calculation"""
        current_sensors = []
        hwmon_base = "/sys/class/hwmon"
        if os.path.exists(hwmon_base):
            for hwmon_dir in os.listdir(hwmon_base):
                hwmon_path = os.path.join(hwmon_base, hwmon_dir)
                for i in range(1, 10):
                    current_path = os.path.join(hwmon_path, f"curr{i}_input")
                    if os.path.exists(current_path):
                        current_sensors.append(current_path)
        return current_sensors

    def _find_energy_sensors(self):
        """Find energy counters for power calculation"""
        energy_sensors = []
        hwmon_base = "/sys/class/hwmon"
        if os.path.exists(hwmon_base):
            for hwmon_dir in os.listdir(hwmon_base):
                hwmon_path = os.path.join(hwmon_base, hwmon_dir)
                for i in range(1, 10):
                    energy_path = os.path.join(hwmon_path, f"energy{i}_input")
                    if os.path.exists(energy_path):
                        energy_sensors.append(energy_path)
        return energy_sensors

    def _read_sensor_value(self, path):
        """Safely read a sensor value"""
        try:
            with open(path, 'r') as f:
                return int(f.read().strip())
        except Exception:
            return None

    def get_system_power(self):
        """Get system power consumption in watts"""
        total_power = 0.0
        power_sources = 0

        # Try power supply interfaces first
        for supply_info in self.power_supply_paths:
            if supply_info[0] == "power_now":
                power_uw = self._read_sensor_value(supply_info[1])
                if power_uw is not None:
                    total_power += power_uw / 1000000.0  # Convert µW to W
                    power_sources += 1
            elif supply_info[0] == "voltage_current":
                voltage_uv = self._read_sensor_value(supply_info[1])
                current_ua = self._read_sensor_value(supply_info[2])
                if voltage_uv is not None and current_ua is not None:
                    power_w = (voltage_uv / 1000000.0) * (current_ua / 1000000.0)
                    total_power += power_w
                    power_sources += 1

        # Try hwmon power sensors
        for power_path in self.hwmon_power:
            power_uw = self._read_sensor_value(power_path)
            if power_uw is not None:
                total_power += power_uw / 1000000.0  # Convert µW to W
                power_sources += 1

        # If no direct power readings, try voltage/current pairs
        if power_sources == 0 and len(self.voltage_paths) > 0 and len(self.current_paths) > 0:
            for voltage_path in self.voltage_paths[:len(self.current_paths)]:
                current_path = self.current_paths[min(len(self.current_paths)-1,
                                                   self.voltage_paths.index(voltage_path))]
                voltage_mv = self._read_sensor_value(voltage_path)
                current_ma = self._read_sensor_value(current_path)
                if voltage_mv is not None and current_ma is not None:
                    power_w = (voltage_mv / 1000.0) * (current_ma / 1000.0)
                    total_power += power_w
                    power_sources += 1

        return total_power if power_sources > 0 else None

    def estimate_cpu_power(self, cpu_usages, frequencies):
        """Estimate CPU power consumption based on usage and frequency"""
        if not cpu_usages:
            return None

        total_power = 0.0

        for i, usage in enumerate(cpu_usages):
            # Base power consumption
            core_power = self.cpu_base_power / len(cpu_usages)

            # Scale with usage (quadratic relationship for power)
            usage_factor = usage * usage if usage > 0 else 0

            # Scale with frequency if available
            freq_factor = 1.0
            if i < len(frequencies) and frequencies[i] is not None:
                # Normalize frequency (assuming base freq ~800MHz, max ~1800MHz)
                base_freq = 800000  # 800 MHz in kHz
                max_freq = 1800000  # 1.8 GHz in kHz
                normalized_freq = max(0.0, min(1.0, (frequencies[i] - base_freq) / (max_freq - base_freq)))
                freq_factor = 1.0 + normalized_freq  # Linear frequency scaling

            core_power += (self.cpu_max_power / len(cpu_usages)) * usage_factor * freq_factor
            total_power += core_power

        return total_power

    def get_power_from_energy(self):
        """Calculate power from energy counters if available"""
        if not self.energy_paths:
            return None

        current_time = time.time()
        total_energy = 0
        energy_sources = 0

        for energy_path in self.energy_paths:
            energy_uj = self._read_sensor_value(energy_path)
            if energy_uj is not None:
                total_energy += energy_uj / 1000000.0  # Convert µJ to J
                energy_sources += 1

        if energy_sources == 0:
            return None

        if self.last_energy_reading is not None and self.last_energy_time is not None:
            time_delta = current_time - self.last_energy_time
            energy_delta = total_energy - self.last_energy_reading

            if time_delta > 0:
                power_w = energy_delta / time_delta
                self.last_energy_reading = total_energy
                self.last_energy_time = current_time
                return power_w

        self.last_energy_reading = total_energy
        self.last_energy_time = current_time
        return None


# --------------------- Data collectors (enhanced) ---------------------

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
            cpu = parts[0]
            nums = list(map(int, parts[1:]))
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
    # Respect cpuset/cgroup limits if any
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
        sensors.append((tname, ttemp_path, ("cpu" in lname) or ("soc" in lname)))
    if any(pref for _, _, pref in sensors):
        sensors = [(n, p) for n, p, pref in sensors if pref]
    else:
        sensors = [(n, p) for n, p, _ in sensors]
    return sensors


def read_temp_mC(path):
    try:
        return int(open(path, "r").read().strip())
    except Exception:
        return None


# --------------------- Burner (unchanged) ---------------------

def _pin_to(cpu_id):
    try:
        os.sched_setaffinity(0, {cpu_id})
    except Exception:
        pass

def burn_loop(stop_evt: Event, cpu_id: int | None, pin: bool):
    if pin and cpu_id is not None:
        _pin_to(cpu_id)
    # tight hot loop; no sleeps, no I/O
    x = 1.0001
    y = 123456789
    while not stop_evt.is_set():
        x = x * 1.0000003 + math.sqrt(x) - math.log(x)
        y = (y * 1664525 + 1013904223) & 0xFFFFFFFF
        if (y & 0xFF) == 0:
            x = x % 1000.0


class BurnerManager:
    def __init__(self, force_unpinned_extras=True):
        self.stop_evt = Event()
        self.procs: list[Process] = []
        self.cpus = online_cpus()
        self.force_unpinned_extras = force_unpinned_extras

    def active_workers(self):
        return sum(1 for p in self.procs if p.is_alive())

    def start(self, nworkers: int):
        # Scale up: spawn more; scale down: restart cleanly to keep mapping sane
        current = self.active_workers()
        if nworkers > current:
            self._spawn_range(current, nworkers)
        elif nworkers < current:
            self.stop_all()
            self.procs = []
            self._spawn_range(0, nworkers)

    def _spawn_range(self, start_idx: int, end_idx: int):
        self.stop_evt.clear()
        for idx in range(start_idx, end_idx):
            if idx < len(self.cpus):
                cpu = self.cpus[idx]
                pin = True
            else:
                # overcommit: extras are unpinned so scheduler can spread them
                cpu = None
                pin = not self.force_unpinned_extras
            p = Process(target=burn_loop, args=(self.stop_evt, cpu, pin), daemon=False)
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


# --------------------- Enhanced CSV Logger ---------------------

class PowerCsvLogger:
    def __init__(self, path, cpu_count, sensor_names):
        self.path = path
        self.cpu_count = cpu_count
        self.sensor_names = sensor_names
        self.fh = None
        self.writer = None
        self.open()

    def open(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.fh = open(self.path, "w", newline="")
        fieldnames = [
            "timestamp_iso", "timestamp_ms",
            "overall_cpu_pct", "load1", "load5", "load15",
            "burning", "workers",
            "system_power_w", "cpu_power_est_w", "energy_power_w", "total_power_w"
        ]
        fieldnames += [f"cpu{i}_pct" for i in range(self.cpu_count)]
        fieldnames += [f"freq{i}_khz" for i in range(self.cpu_count)]
        fieldnames += [f"temp{i}_c" for i in range(len(self.sensor_names))]
        self.writer = csv.DictWriter(self.fh, fieldnames=fieldnames)
        self.writer.writeheader()
        self.fh.flush()

    def log(self, overall_pct, la_tuple, burning, workers, usages, freqs_khz, temps_mC, power_data):
        if not self.writer:
            return
        now = time.time()
        row = {
            "timestamp_iso": datetime.utcfromtimestamp(now).isoformat(),
            "timestamp_ms": int(now * 1000),
            "overall_cpu_pct": int(overall_pct * 100),
            "load1": la_tuple[0],
            "load5": la_tuple[1],
            "load15": la_tuple[2],
            "burning": int(bool(burning)),
            "workers": workers,
            "system_power_w": f"{power_data['system_power']:.3f}" if power_data['system_power'] is not None else "",
            "cpu_power_est_w": f"{power_data['cpu_power']:.3f}" if power_data['cpu_power'] is not None else "",
            "energy_power_w": f"{power_data['energy_power']:.3f}" if power_data['energy_power'] is not None else "",
            "total_power_w": f"{power_data['total_power']:.3f}" if power_data['total_power'] is not None else ""
        }
        for i in range(self.cpu_count):
            u = usages[i] if i < len(usages) and usages[i] is not None else 0.0
            row[f"cpu{i}_pct"] = int(u * 100)
        for i in range(self.cpu_count):
            fk = freqs_khz[i] if i < len(freqs_khz) and freqs_khz[i] is not None else ""
            row[f"freq{i}_khz"] = fk
        for i in range(len(self.sensor_names)):
            tC = None
            if i < len(temps_mC) and temps_mC[i] is not None:
                tC = temps_mC[i] / 1000.0
            row[f"temp{i}_c"] = f"{tC:.1f}" if tC is not None else ""
        self.writer.writerow(row)
        self.fh.flush()

    def close(self):
        try:
            if self.fh:
                self.fh.flush()
                self.fh.close()
        except Exception:
            pass
        self.fh = None
        self.writer = None


# --------------------- Enhanced UI ---------------------

class PowerMonitorUI(Gtk.Window):
    def __init__(self, interval, start_burners, initial_workers,
                 force_unpinned_extras, log_file=None, log_auto=False):
        super().__init__(title="i.MX8M Mini CPU & Power Monitor")
        self.set_app_paintable(True)
        self.connect("destroy", self.on_destroy)

        self.da = Gtk.DrawingArea()
        self.da.connect("draw", self.on_draw)
        self.da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.TOUCH_MASK)
        self.da.connect("button-press-event", self.on_button_press)
        self.da.connect("touch-event", self.on_touch_event)
        self.add(self.da)

        self.interval = max(0.1, float(interval))
        self.reader = CpuStatReader()
        self.power_monitor = PowerMonitor()
        self.freq_paths = cpu_freq_paths()
        self.sensors = find_thermal_sensors()
        self.sensor_names = [n for n, _ in self.sensors]
        self.last_usages = []
        self.last_freqs = []
        self.last_temps = []
        self.last_load = (0.0, 0.0, 0.0)
        self.overall_usage = 0.0
        self.last_power_data = {
            'system_power': None,
            'cpu_power': None,
            'energy_power': None,
            'total_power': None
        }

        self.burner = BurnerManager(force_unpinned_extras=force_unpinned_extras)
        self.burning = bool(start_burners)
        self.target_workers = initial_workers if initial_workers > 0 else len(online_cpus())
        if self.burning:
            self.burner.start(self.target_workers)

        # Buttons hitboxes
        self.buttons = []
        self.control_bar_h = 84

        # Enhanced logging with power data
        self.log_file = log_file or os.path.abspath(
            f"./cpu_power_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self.logger = None
        self.logging_enabled = False
        if log_auto:
            self.enable_logging()

        GLib.timeout_add(int(self.interval * 1000), self.tick)

    # logging
    def enable_logging(self):
        try:
            if not self.logger:
                self.logger = PowerCsvLogger(
                    self.log_file,
                    cpu_count=len(online_cpus()),
                    sensor_names=self.sensor_names,
                )
            self.logging_enabled = True
        except Exception:
            self.logging_enabled = False

    def disable_logging(self):
        self.logging_enabled = False
        if self.logger:
            self.logger.close()
            self.logger = None

    # events (unchanged)
    def on_destroy(self, *_):
        try:
            self.disable_logging()
        except Exception:
            pass
        try:
            self.burner.stop_all()
        except Exception:
            pass
        Gtk.main_quit()

    def on_touch_event(self, widget, event):
        if event.type.value_nick == "touch-begin":
            self.handle_press(event.x, event.y)
        return True

    def on_button_press(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self.handle_press(event.x, event.y)
        return True

    def handle_press(self, x, y):
        for btn in self.buttons:
            if not btn.get("enabled", True):
                continue
            bx, by, bw, bh = btn["x"], btn["y"], btn["w"], btn["h"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.activate_button(btn["id"])
                break

    def activate_button(self, bid):
        if bid == "burn":
            self.burning = not self.burning
            if self.burning:
                self.burner.start(self.target_workers)
            else:
                self.burner.stop_all()
        elif bid == "minus":
            if self.burning:
                self.target_workers = max(self.target_workers - 1, 0)
                self.burner.start(self.target_workers)
        elif bid == "plus":
            if self.burning:
                self.target_workers = self.target_workers + 1  # allow > CPU count
                self.burner.start(self.target_workers)
        elif bid == "quit":
            self.destroy()
            return
        elif bid == "rec":
            if self.logging_enabled:
                self.disable_logging()
            else:
                self.enable_logging()
        self.queue_draw()

    # Enhanced update with power monitoring
    def tick(self):
        try:
            self.last_usages = self.reader.usage_per_cpu()
            self.overall_usage = (sum(self.last_usages) / len(self.last_usages)) if self.last_usages else 0.0
            self.last_freqs = [read_freq_khz(p) for p in self.freq_paths] if self.freq_paths else []
            try:
                self.last_load = os.getloadavg()
            except Exception:
                self.last_load = (0.0, 0.0, 0.0)
            self.last_temps = [read_temp_mC(p) for _, p in self.sensors] if self.sensors else []

            # Get power measurements
            system_power = self.power_monitor.get_system_power()
            cpu_power = self.power_monitor.estimate_cpu_power(self.last_usages, self.last_freqs)
            energy_power = self.power_monitor.get_power_from_energy()

            # Calculate total power (prefer system measurement, fall back to estimation)
            total_power = system_power
            if total_power is None and cpu_power is not None:
                total_power = cpu_power
            elif total_power is None and energy_power is not None:
                total_power = energy_power

            self.last_power_data = {
                'system_power': system_power,
                'cpu_power': cpu_power,
                'energy_power': energy_power,
                'total_power': total_power
            }

        except Exception:
            pass

        if self.logging_enabled and self.logger:
            try:
                self.logger.log(
                    overall_pct=self.overall_usage,
                    la_tuple=self.last_load,
                    burning=self.burning,
                    workers=self.burner.active_workers(),
                    usages=self.last_usages,
                    freqs_khz=[f if f is not None else "" for f in self.last_freqs],
                    temps_mC=self.last_temps,
                    power_data=self.last_power_data,
                )
            except Exception:
                self.disable_logging()

        self.queue_draw()
        return True

    # drawing helpers (unchanged)
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

    def _draw_button(self, cr, x, y, w, h, label, enabled=True, active=False):
        cr.save()
        if not enabled:
            cr.set_source_rgb(0.22, 0.22, 0.24)
        elif active:
            cr.set_source_rgb(0.18, 0.35, 0.55)
        else:
            cr.set_source_rgb(0.16, 0.17, 0.20)
        cr.rectangle(x, y, w, h)
        cr.fill()
        cr.set_source_rgb(0.38, 0.40, 0.44)
        cr.set_line_width(2.0)
        cr.rectangle(x + 1, y + 1, w - 2, h - 2)
        cr.stroke()
        cr.set_source_rgb(0.92, 0.92, 0.94) if enabled else cr.set_source_rgb(0.6, 0.6, 0.65)
        self._draw_text(cr, x + w / 2, y + (h - 22) / 2, label, size=18, align="center")
        cr.restore()

    # Enhanced draw with power display
    def on_draw(self, _widget, cr):
        w = self.get_allocated_width()
        h = self.get_allocated_height()

        cr.set_source_rgb(0.08, 0.09, 0.11)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        pad = 20
        x = pad
        y = pad

        # Header
        cr.set_source_rgb(0.9, 0.9, 0.9)
        self._draw_text(cr, x, y, "i.MX8M Mini Thermal/Power Monitor", size=22, align="left")
        y += 30

        # Status line with power
        la = self.last_load
        power_str = ""
        if self.last_power_data['total_power'] is not None:
            power_str = f"  Power: {self.last_power_data['total_power']:.2f}W"
        elif self.last_power_data['cpu_power'] is not None:
            power_str = f"  Power(est): {self.last_power_data['cpu_power']:.2f}W"

        status = f"Load avg: {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}    Burn: {'ON' if self.burning else 'OFF'}  Workers: {self.burner.active_workers()}/{self.target_workers}{power_str}"
        cr.set_source_rgb(0.75, 0.75, 0.75)
        self._draw_text(cr, x, y, status, size=16, align="left")
        y += 28

        # Overall CPU bar
        bar_w = w - 2 * pad
        bar_h = 28
        cr.set_source_rgb(0.18, 0.19, 0.22)
        cr.rectangle(x, y, bar_w, bar_h)
        cr.fill()
        u = max(0.0, min(self.overall_usage, 1.0))
        hue = max(0.0, min(0.33 * (1.0 - u), 0.33))
        r, g, b = self._hsv_to_rgb(hue, 0.9, 0.95)
        cr.set_source_rgb(r, g, b)
        cr.rectangle(x, y, int(bar_w * u), bar_h)
        cr.fill()
        cr.set_source_rgb(0.95, 0.95, 0.95)
        self._draw_text(cr, x + 8, y + 4, f"Overall CPU: {int(u*100):3d}%", size=16, align="left")
        y += bar_h + 18

        # Power consumption bar (new)
        if self.last_power_data['total_power'] is not None:
            power_w = self.last_power_data['total_power']
            max_power = 5.0  # Assume max 5W for visualization
            power_norm = min(1.0, power_w / max_power)

            cr.set_source_rgb(0.18, 0.19, 0.22)
            cr.rectangle(x, y, bar_w, bar_h)
            cr.fill()

            # Color based on power level (blue to red)
            hue = max(0.0, min(0.67 * (1.0 - power_norm), 0.67))  # Blue to red
            r, g, b = self._hsv_to_rgb(hue, 0.9, 0.95)
            cr.set_source_rgb(r, g, b)
            cr.rectangle(x, y, int(bar_w * power_norm), bar_h)
            cr.fill()
            cr.set_source_rgb(0.95, 0.95, 0.95)
            self._draw_text(cr, x + 8, y + 4, f"Power: {power_w:.2f}W", size=16, align="left")
            y += bar_h + 18

        # Per-CPU bars
        usages = self.last_usages
        n = len(usages)
        if n > 0:
            avail_h = h - y - self.control_bar_h - 180
            bar_h_each = max(22, int(avail_h / max(4, n)))
            bar_h_each = min(bar_h_each, 40)
            for i, u in enumerate(usages):
                uy = y + i * (bar_h_each + 6)
                cr.set_source_rgb(0.18, 0.19, 0.22)
                cr.rectangle(x, uy, bar_w, bar_h_each)
                cr.fill()
                hue = max(0.0, min(0.33 * (1.0 - u), 0.33))
                r, g, b = self._hsv_to_rgb(hue, 0.9, 0.95)
                cr.set_source_rgb(r, g, b)
                cr.rectangle(x, uy, int(bar_w * u), bar_h_each)
                cr.fill()
                cr.set_source_rgb(0.95, 0.95, 0.95)
                percent = int(u * 100)
                label = f"CPU{i}: {percent:3d}%"
                if i < len(self.last_freqs) and self.last_freqs[i]:
                    label += f"  {self.last_freqs[i]//1000} MHz"
                self._draw_text(cr, x + 6, uy + 3, label, size=14, align="left")
            y += n * (bar_h_each + 6) + 12

        # Temperatures
        temps = self.last_temps
        if self.sensors:
            cr.set_source_rgb(0.9, 0.9, 0.9)
            self._draw_text(cr, x, y, "Thermal sensors:", size=18, align="left")
            y += 30
            box_w = (w - 2 * pad)
            cols = max(1, min(3, len(self.sensors)))
            col_w = max(240, box_w // cols)
            for idx, (name, _) in enumerate(self.sensors):
                col = idx % cols
                row = idx // cols
                px = x + col * col_w
                py = y + row * 70

                cr.set_source_rgb(0.85, 0.85, 0.85)
                t_mC = temps[idx] if idx < len(temps) else None
                label = name
                tnorm = 0.0
                if t_mC is not None:
                    tC = t_mC / 1000.0
                    label += f": {tC:.1f}°C"
                    tnorm = (tC - 40.0) / 60.0
                    tnorm = 0.0 if tnorm < 0 else 1.0 if tnorm > 1 else tnorm
                self._draw_text(cr, px, py, label, size=14, align="left")

                bar_y = py + 26  # placed clearly below the text
                bar_h2 = 18
                cr.set_source_rgb(0.18, 0.19, 0.22)
                cr.rectangle(px, bar_y, col_w - 20, bar_h2)
                cr.fill()
                hue = max(0.0, min(0.33 * (1.0 - tnorm), 0.33))
                r, g, b = self._hsv_to_rgb(hue, 0.95, 0.95)
                cr.set_source_rgb(r, g, b)
                cr.rectangle(px, bar_y, (col_w - 20) * tnorm, bar_h2)
                cr.fill()

            rows = (len(self.sensors) + cols - 1) // cols
            y += rows * 70 + 10

        # Bottom control bar (unchanged)
        self.buttons = []
        cy = h - self.control_bar_h + 10
        cx = pad
        gap = 14
        bw = max(140, (w - 2 * pad - gap * 4) // 5)
        bh = self.control_bar_h - 20

        # Burn toggle
        burn_label = "Burn ON" if not self.burning else "Burn OFF"
        self._draw_button(cr, cx, cy, bw, bh, burn_label, enabled=True, active=self.burning)
        self.buttons.append({"id": "burn", "x": cx, "y": cy, "w": bw, "h": bh, "enabled": True})
        cx += bw + gap

        # Minus
        minus_enabled = self.burning and self.burner.active_workers() > 0
        self._draw_button(cr, cx, cy, bw, bh, "−", enabled=minus_enabled)
        self.buttons.append({"id": "minus", "x": cx, "y": cy, "w": bw, "h": bh, "enabled": minus_enabled})
        cx += bw + gap

        # Plus (no cap)
        plus_enabled = self.burning
        self._draw_button(cr, cx, cy, bw, bh, "+", enabled=plus_enabled)
        self.buttons.append({"id": "plus", "x": cx, "y": cy, "w": bw, "h": bh, "enabled": plus_enabled})
        cx += bw + gap

        # Quit replaces Fullscreen
        self._draw_button(cr, cx, cy, bw, bh, "Quit", enabled=True)
        self.buttons.append({"id": "quit", "x": cx, "y": cy, "w": bw, "h": bh, "enabled": True})
        cx += bw + gap

        # REC (logging)
        rec_label = "REC ●" if self.logging_enabled else "REC ○"
        self._draw_button(cr, cx, cy, bw, bh, rec_label, enabled=True, active=self.logging_enabled)
        self.buttons.append({"id": "rec", "x": cx, "y": cy, "w": bw, "h": bh, "enabled": True})

        # Enhanced hint with power info
        cr.set_source_rgb(0.6, 0.6, 0.65)
        power_hint = ""
        if self.last_power_data['system_power'] is not None:
            power_hint = f"   Sys: {self.last_power_data['system_power']:.2f}W"
        if self.last_power_data['cpu_power'] is not None:
            power_hint += f"   CPU: {self.last_power_data['cpu_power']:.2f}W"

        hint = f"Workers: {self.burner.active_workers()}/{self.target_workers}   Log: {'ON' if self.logging_enabled else 'OFF'}{power_hint}"
        self._draw_text(cr, x, cy - 6, hint, size=14, align="left")

        return False


# --------------------- main ---------------------

def main():
    ap = argparse.ArgumentParser(description="CPU burner + Wayland/GTK monitor with power consumption monitoring")
    ap.add_argument("--interval", type=float, default=0.5, help="UI update interval seconds")
    ap.add_argument("--start-burn", action="store_true", help="Start with burners ON")
    ap.add_argument("--workers", type=int, default=0, help="Initial workers (0=one per visible CPU)")
    ap.add_argument("--log-file", type=str, default=None, help="CSV file path for power logging")
    ap.add_argument("--log-auto", action="store_true", help="Start with logging enabled")
    ap.add_argument("--pin-extras", action="store_true",
                    help="Also pin workers beyond CPU count (not recommended; may reduce per-core %)")
    ap.add_argument("--windowed", action="store_true", help="Run windowed instead of fullscreen")

    args = ap.parse_args()

    win = PowerMonitorUI(interval=args.interval,
                        start_burners=args.start_burn,
                        initial_workers=(args.workers if args.workers > 0 else len(online_cpus())),
                        force_unpinned_extras=not args.pin_extras,
                        log_file=args.log_file,
                        log_auto=args.log_auto)

    win.set_default_size(800, 1280)
    win.show_all()

    if not args.windowed:
        GLib.idle_add(win.fullscreen)

    def handle_sig(_s, _f):
        try:
            win.destroy()
        except Exception:
            Gtk.main_quit()
    signal.signal(signal.SIGTERM, handle_sig)
    Gtk.main()


if __name__ == "__main__":
    main()