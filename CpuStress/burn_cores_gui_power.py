#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Wayland/Weston CPU burner + live monitor (GTK3 + Cairo) with touch controls, CSV logging, and POWER MONITORING.
# Extended version with LTC2959IDDBTRMPBF I2C power monitoring chip.
#
# New features:
# - Power consumption monitoring via LTC2959IDDBTRMPBF I2C chip (bus 3, address 0x63)
# - Real power measurements (voltage, current, power)
# - Real-time power draw visualization
#
# Touch controls (bottom bar):
#   [Burn ON/OFF]  [−]  [+]  [Quit]  [REC]
#
# CSV now includes:
#   - voltage_v, current_a, power_w (real measurements from LTC2959)
#   - voltage_raw, current_raw, power_raw (raw register values)
#
# Usage:
#   --log-file PATH (default ./cpu_monitor_YYYYmmdd_HHMMSS.csv)
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

try:
    from smbus import SMBus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    print("Warning: smbus not available, power monitoring disabled")


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


class LTC2959PowerMonitor:
    """Monitor power consumption via LTC2959IDDBTRMPBF I2C chip"""

    def __init__(self, bus_number=3, address=0x63):
        self.bus_number = bus_number
        self.address = address
        self.bus = None
        self.available = False

        # LTC2959 register addresses (from datasheet)
        self.REG_STATUS = 0x00           # Status register A
        self.REG_ADC_CONTROL = 0x01      # ADC Control register B (main config)
        self.REG_COULOMB_CONFIG = 0x02   # Coulomb Counter Config register C

        # Measurement result registers (from datasheet register map)
        self.REG_VOLTAGE_MSB = 0x0F      # Voltage MSB (register P)
        self.REG_VOLTAGE_LSB = 0x10      # Voltage LSB (register Q)
        self.REG_CURRENT_MSB = 0x19      # Current MSB (register Z) - signed
        self.REG_CURRENT_LSB = 0x1A      # Current LSB (register AA) - signed

        # Register aliases for compatibility
        self.REG_VSENSE_H = self.REG_VOLTAGE_MSB
        self.REG_VSENSE_L = self.REG_VOLTAGE_LSB
        self.REG_ISENSE_H = self.REG_CURRENT_MSB
        self.REG_ISENSE_L = self.REG_CURRENT_LSB

        # Power register (not used - we calculate P = V * I)
        self.REG_POWER_H = 0x04
        self.REG_POWER_L = 0x05

        # ADC configuration values (from datasheet Table B[7:5])
        self.ADC_MODE_SLEEP = 0b000 << 5              # [000] Sleep mode
        self.ADC_MODE_SMART_SLEEP = 0b001 << 5        # [001] Smart sleep (every 52s)
        self.ADC_MODE_CONT_VOLTAGE = 0b010 << 5       # [010] Continuous V (2.5kS/s)
        self.ADC_MODE_CONT_CURRENT = 0b011 << 5       # [011] Continuous I (2.5kS/s)
        self.ADC_MODE_CONT_V_I_ALT = 0b100 << 5       # [100] Continuous V and I alternating ⭐
        self.ADC_MODE_SINGLE_SHOT = 0b101 << 5        # [101] Single-shot V, I, T
        self.ADC_MODE_CONT_V_I_T = 0b110 << 5         # [110] Continuous V, I, T cycle

        # GPIO and voltage input configuration
        self.GPIO_CONFIG_ALERT = 0b00 << 3            # [00] Alert mode output
        self.GPIO_CONFIG_CHARGE_COMPLETE = 0b01 << 3  # [01] Charge complete input
        self.GPIO_CONFIG_ANALOG_SMALL = 0b10 << 3     # [10] ±97.5mV range
        self.GPIO_CONFIG_ANALOG_LARGE = 0b11 << 3     # [11] 0-1.56V range (default)

        self.VOLTAGE_INPUT_VDD = 0 << 2               # B[2]=0: Use VDD as voltage input ⭐
        self.VOLTAGE_INPUT_SENSEN = 1 << 2            # B[2]=1: Use SENSEN as voltage input

        # Scaling factors (from datasheet specifications)
        # For voltage: VDD measurement, full scale 62.6V, 16-bit resolution
        self.voltage_scale = 62.6 / 65536             # 0.955 mV per LSB (from datasheet)

        # For current: ±97.5mV full scale across sense resistor, 16-bit resolution
        # Current = (VSENSE / RSENSE), from datasheet formula page 14
        self.current_lsb = 97.5e-3 / 32768            # 2.975 µV per LSB (signed, from datasheet)
        self.sense_resistor = 0.010                   # 10mΩ sense resistor (0.010Ω, 1W, 1%)
        self.current_scale = self.current_lsb / self.sense_resistor  # A per LSB

        # For power: we calculate P = V * I rather than using power register
        # But keep power_scale for compatibility (not used in our implementation)
        self.power_scale = 1.0  # Placeholder - we calculate power as V * I

        self._initialize()

        # Configure the chip for continuous V+I alternating mode after initialization
        if self.available:
            self.configure_continuous_mode()


    def _initialize(self):
        """Initialize the LTC2959 I2C connection"""
        if not SMBUS_AVAILABLE:
            print("LTC2959PowerMonitor: smbus not available")
            return

        try:
            self.bus = SMBus(self.bus_number)

            # Test communication by reading voltage register
            voltage_msb = self.bus.read_byte_data(self.address, self.REG_VSENSE_H)
            voltage_lsb = self.bus.read_byte_data(self.address, self.REG_VSENSE_L)
            voltage_raw = (voltage_msb << 8) | voltage_lsb

            # Read current and power to verify chip is responsive
            current_raw = self.read_16bit_register(self.REG_ISENSE_H, self.REG_ISENSE_L)
            power_raw = self.read_16bit_register(self.REG_POWER_H, self.REG_POWER_L)

            print(f"LTC2959PowerMonitor: Successfully connected on bus {self.bus_number}, address 0x{self.address:02X}")
            print(f"LTC2959PowerMonitor: Initial readings - V:{voltage_raw}, I:{current_raw}, P:{power_raw}")

            # The LTC2959 is already in continuous measurement mode
            self.available = True
            print("LTC2959PowerMonitor: Ready for continuous power measurements")

        except Exception as e:
            self.available = False
            print(f"LTC2959PowerMonitor: Failed to initialize: {e}")

    def configure_continuous_mode(self):
        """Configure the LTC2959 for continuous V+I alternating mode with VDD voltage input"""
        if not self.available:
            print("LTC2959: Cannot configure - device not available")
            return False

        print("LTC2959: Configuring for continuous V+I alternating mode...")

        # Read current ADC Control register (Register B)
        current_config = self.read_register(self.REG_ADC_CONTROL)
        if current_config is None:
            print("LTC2959: Failed to read current configuration")
            return False

        print(f"LTC2959: Current ADC Control register: 0x{current_config:02X}")

        # Configure Register B (ADC Control) according to datasheet
        # Bits [7:5] = 100 (Continuous V and I alternating)
        # Bit [2] = 0 (Use VDD as voltage input)
        # Other bits: keep as default (0)
        new_config = (
            self.ADC_MODE_CONT_V_I_ALT |     # [7:5] = 100: Continuous V+I alternating
            self.VOLTAGE_INPUT_VDD           # [2] = 0: Use VDD as voltage input
        )
        # Bits [4:3] and [1:0] remain 0 (default values)

        print(f"LTC2959: Writing new configuration: 0x{new_config:02X}")

        if not self.write_register(self.REG_ADC_CONTROL, new_config):
            return False

        # Verify the configuration was written
        import time
        time.sleep(0.01)  # 10ms delay for register write to take effect

        verify_config = self.read_register(self.REG_ADC_CONTROL)
        if verify_config == new_config:
            print(f"LTC2959: Configuration verified: 0x{verify_config:02X}")
            print("LTC2959: Now measuring V+I alternating at 1250 samples/sec each")
            return True
        else:
            print(f"LTC2959: Configuration mismatch - wrote 0x{new_config:02X}, read 0x{verify_config:02X}")
            return False

    def write_register(self, register, value):
        """Write a single byte to a register"""
        try:
            self.bus.write_byte_data(self.address, register, value)
            print(f"LTC2959: Wrote 0x{value:02X} to register 0x{register:02X}")
            return True
        except Exception as e:
            print(f"LTC2959PowerMonitor: Error writing register 0x{register:02X}: {e}")
            return False

    def read_register(self, register):
        """Read a single byte from a register"""
        try:
            value = self.bus.read_byte_data(self.address, register)
            return value
        except Exception as e:
            print(f"LTC2959PowerMonitor: Error reading register 0x{register:02X}: {e}")
            return None

    def read_16bit_register(self, msb_reg, lsb_reg):
        """Read a 16-bit value from two 8-bit registers"""
        try:
            msb = self.bus.read_byte_data(self.address, msb_reg)
            lsb = self.bus.read_byte_data(self.address, lsb_reg)
            return (msb << 8) | lsb
        except Exception as e:
            print(f"LTC2959PowerMonitor: Error reading registers 0x{msb_reg:02X}/0x{lsb_reg:02X}: {e}")
            return None

    def read_voltage(self):
        """Read voltage measurement"""
        raw_value = self.read_16bit_register(self.REG_VSENSE_H, self.REG_VSENSE_L)
        if raw_value is not None:
            voltage = raw_value * self.voltage_scale
            return voltage, raw_value
        return None, None

    def read_current(self):
        """Read current measurement (handles signed values)"""
        raw_value = self.read_16bit_register(self.REG_ISENSE_H, self.REG_ISENSE_L)
        if raw_value is not None:
            # Convert to signed 16-bit value (two's complement)
            if raw_value > 32767:  # If MSB is set (negative value)
                signed_raw = raw_value - 65536
            else:
                signed_raw = raw_value

            # Apply current scaling: I = (VSENSE / RSENSE)
            # where VSENSE = signed_raw * current_lsb
            current = signed_raw * self.current_scale
            return current, raw_value  # Return current in Amps and original raw value
        return None, None

    def read_power(self):
        """Read power measurement"""
        raw_value = self.read_16bit_register(self.REG_POWER_H, self.REG_POWER_L)
        if raw_value is not None:
            power = raw_value * self.power_scale
            return power, raw_value
        return None, None

    def is_data_ready(self):
        """Check if new measurement data is available (for continuous mode)"""
        # In continuous alternating mode, we could check a status register
        # For now, we'll assume data is always ready since we're sampling at 1250Hz
        # This method can be enhanced if the LTC2959 provides a data-ready flag
        return True

    def read_all_measurements(self):
        """Read all power measurements (optimized for continuous mode)"""
        if not self.available:
            return {
                'voltage_v': None,
                'current_a': None,
                'power_w': None,
                'voltage_raw': None,
                'current_raw': None,
                'power_raw': None,
                'timestamp': time.time()
            }

        # In continuous alternating mode, we get fresh data at 1250 samples/sec
        # so we can read directly without waiting
        voltage, voltage_raw = self.read_voltage()
        current, current_raw = self.read_current()

        # Calculate power from voltage and current (more accurate than reading power register)
        # Also read the power register for comparison
        power_calc = None
        if voltage is not None and current is not None:
            power_calc = voltage * current  # P = V * I

        power, power_raw = self.read_power()

        # Use calculated power if available, otherwise use power register reading
        final_power = power_calc if power_calc is not None else power

        return {
            'voltage_v': voltage,
            'current_a': current,
            'power_w': final_power,
            'power_calc_w': power_calc,  # Calculated P = V * I
            'power_reg_w': power,        # Power register reading
            'voltage_raw': voltage_raw,
            'current_raw': current_raw,
            'power_raw': power_raw,
            'timestamp': time.time()
        }

    def calibrate(self, known_voltage=None, known_current=None, known_power=None):
        """
        Calibrate the sensor readings with known values
        This should be called with known reference values for accurate measurements
        """
        if known_voltage:
            _, raw_v = self.read_voltage()
            if raw_v and raw_v > 0:
                self.voltage_scale = known_voltage / raw_v
                print(f"LTC2959: Voltage calibrated - scale = {self.voltage_scale:.6f} V/LSB")

        if known_current:
            _, raw_i = self.read_current()
            if raw_i and raw_i > 0:
                self.current_scale = known_current / raw_i
                print(f"LTC2959: Current calibrated - scale = {self.current_scale:.6f} A/LSB")

        if known_power:
            _, raw_p = self.read_power()
            if raw_p and raw_p > 0:
                self.power_scale = known_power / raw_p
                print(f"LTC2959: Power calibrated - scale = {self.power_scale:.6f} W/LSB")


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


# --------------------- Burner ---------------------

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


# --------------------- CSV Logger ---------------------

class CsvLogger:
    def __init__(self, path, cpu_count, sensor_names, power_enabled=False):
        self.path = path
        self.cpu_count = cpu_count
        self.sensor_names = sensor_names
        self.power_enabled = power_enabled
        self.fh = None
        self.writer = None
        self.open()

    def open(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.fh = open(self.path, "w", newline="")
        fieldnames = [
            "timestamp_iso", "timestamp_ms",
            "overall_cpu_pct", "load1", "load5", "load15",
            "burning", "workers"
        ]
        fieldnames += [f"cpu{i}_pct" for i in range(self.cpu_count)]
        fieldnames += [f"freq{i}_khz" for i in range(self.cpu_count)]
        fieldnames += [f"temp{i}_c" for i in range(len(self.sensor_names))]

        # Add LTC2959 power monitoring fields
        if self.power_enabled:
            fieldnames += ["voltage_v", "current_a", "power_w"]
            fieldnames += ["voltage_raw", "current_raw", "power_raw"]

        self.writer = csv.DictWriter(self.fh, fieldnames=fieldnames)
        self.writer.writeheader()
        self.fh.flush()

    def log(self, overall_pct, la_tuple, burning, workers, usages, freqs_khz, temps_mC, power_data=None):
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
            "workers": workers
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

        # Add LTC2959 power data if available
        if self.power_enabled and power_data:
            voltage = power_data.get('voltage_v')
            current = power_data.get('current_a')
            power = power_data.get('power_w')
            voltage_raw = power_data.get('voltage_raw')
            current_raw = power_data.get('current_raw')
            power_raw = power_data.get('power_raw')

            row["voltage_v"] = f"{voltage:.3f}" if voltage is not None else ""
            row["current_a"] = f"{current:.3f}" if current is not None else ""
            row["power_w"] = f"{power:.3f}" if power is not None else ""
            row["voltage_raw"] = f"{voltage_raw}" if voltage_raw is not None else ""
            row["current_raw"] = f"{current_raw}" if current_raw is not None else ""
            row["power_raw"] = f"{power_raw}" if power_raw is not None else ""

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


# --------------------- UI ---------------------

class MonitorUI(Gtk.Window):
    def __init__(self, interval, start_burners, initial_workers,
                 force_unpinned_extras, log_file=None, log_auto=False):
        super().__init__(title="i.MX8M Mini CPU + LTC2959 Power Monitor")
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
        self.freq_paths = cpu_freq_paths()
        self.sensors = find_thermal_sensors()
        self.sensor_names = [n for n, _ in self.sensors]
        self.last_usages = []
        self.last_freqs = []
        self.last_temps = []
        self.last_load = (0.0, 0.0, 0.0)
        self.overall_usage = 0.0

        # LTC2959 Power monitoring
        self.power_monitor = LTC2959PowerMonitor()
        self.last_power_data = {
            'voltage_v': None,
            'current_a': None,
            'power_w': None,
            'voltage_raw': None,
            'current_raw': None,
            'power_raw': None
        }

        self.burner = BurnerManager(force_unpinned_extras=force_unpinned_extras)
        self.burning = bool(start_burners)
        self.target_workers = initial_workers if initial_workers > 0 else len(online_cpus())
        if self.burning:
            self.burner.start(self.target_workers)

        # Buttons hitboxes
        self.buttons = []
        self.control_bar_h = 84

        # Logging
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
                self.logger = CsvLogger(
                    self.log_file,
                    cpu_count=len(online_cpus()),
                    sensor_names=self.sensor_names,
                    power_enabled=self.power_monitor.available,
                )
            self.logging_enabled = True
        except Exception:
            self.logging_enabled = False

    def disable_logging(self):
        self.logging_enabled = False
        if self.logger:
            self.logger.close()
            self.logger = None

    # events
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

    # update
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

            # Read LTC2959 power data
            if self.power_monitor.available:
                try:
                    new_power_data = self.power_monitor.read_all_measurements()
                    if new_power_data:
                        self.last_power_data = new_power_data
                        # Debug: print power data every 10 seconds (adjust interval as needed)
                        if hasattr(self, '_debug_counter'):
                            self._debug_counter += 1
                        else:
                            self._debug_counter = 0

                        if self._debug_counter % 4 == 0:  # Every 4 ticks at 0.5s = 2 seconds
                            power = self.last_power_data.get('power_w')
                            voltage = self.last_power_data.get('voltage_v')
                            current = self.last_power_data.get('current_a')
                            power_calc = self.last_power_data.get('power_calc_w')
                            power_reg = self.last_power_data.get('power_reg_w')
                            v_raw = self.last_power_data.get('voltage_raw')
                            i_raw = self.last_power_data.get('current_raw')
                            p_raw = self.last_power_data.get('power_raw')
                            print(f"LTC2959 Update: V={voltage:.3f}V({v_raw}), I={current:.3f}A({i_raw}), P={power:.3f}W({p_raw}) [calc={power_calc:.3f}W, reg={power_reg:.3f}W]")
                except Exception as e:
                    print(f"Error reading LTC2959 data: {e}")
                    # Keep last known values on error
            else:
                if not hasattr(self, '_power_warning_shown'):
                    print("LTC2959 power monitor not available")
                    self._power_warning_shown = True
        except Exception as e:
            print(f"Error in tick(): {e}")

        if self.logging_enabled and self.logger:
            try:
                power_data = self.last_power_data if self.power_monitor.available else None
                self.logger.log(
                    overall_pct=self.overall_usage,
                    la_tuple=self.last_load,
                    burning=self.burning,
                    workers=self.burner.active_workers(),
                    usages=self.last_usages,
                    freqs_khz=[f if f is not None else "" for f in self.last_freqs],
                    temps_mC=self.last_temps,
                    power_data=power_data,
                )
            except Exception:
                self.disable_logging()

        self.queue_draw()
        return True

    # drawing helpers
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

    # draw
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
        power_status = " + LTC2959" if self.power_monitor.available else ""
        self._draw_text(cr, x, y, f"i.MX8M Mini Thermal/Load Monitor{power_status}", size=22, align="left")
        y += 30

        # Status line
        la = self.last_load
        status = f"Load avg: {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}    Burn: {'ON' if self.burning else 'OFF'}  Workers: {self.burner.active_workers()}/{self.target_workers}"
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

        # LTC2959 Power consumption section
        if self.power_monitor.available:
            cr.set_source_rgb(0.9, 0.9, 0.9)
            self._draw_text(cr, x, y, "LTC2959 Power Monitor:", size=18, align="left")
            y += 24

            voltage = self.last_power_data.get('voltage_v')
            current = self.last_power_data.get('current_a')
            power = self.last_power_data.get('power_w')
            voltage_raw = self.last_power_data.get('voltage_raw')
            current_raw = self.last_power_data.get('current_raw')
            power_raw = self.last_power_data.get('power_raw')

            # Power measurements - main values
            measurements = [
                ("Voltage:", f"{voltage:.3f} V" if voltage is not None else "N/A"),
                ("Current:", f"{current:.3f} A" if current is not None else "N/A"),
                ("Power:", f"{power:.3f} W" if power is not None else "N/A")
            ]

            for i, (label, value) in enumerate(measurements):
                cr.set_source_rgb(0.85, 0.85, 0.85)
                self._draw_text(cr, x, y, f"{label} {value}", size=16, align="left")
                y += 22

            # Raw values (smaller text)
            y += 5
            raw_measurements = [
                ("Raw V:", f"0x{voltage_raw:04X} ({voltage_raw})" if voltage_raw is not None else "N/A"),
                ("Raw I:", f"0x{current_raw:04X} ({current_raw})" if current_raw is not None else "N/A"),
                ("Raw P:", f"0x{power_raw:04X} ({power_raw})" if power_raw is not None else "N/A")
            ]

            for i, (label, value) in enumerate(raw_measurements):
                cr.set_source_rgb(0.65, 0.65, 0.65)
                self._draw_text(cr, x, y, f"{label} {value}", size=12, align="left")
                y += 18

            y += 15

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

        # Bottom control bar
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

        # Hint
        cr.set_source_rgb(0.6, 0.6, 0.65)
        power_hint = f"  LTC2959: {'ON' if self.power_monitor.available else 'OFF'}"
        hint = f"Workers alive: {self.burner.active_workers()}   Target: {self.target_workers}   Logging: {'ON' if self.logging_enabled else 'OFF'} ({os.path.basename(self.log_file)}){power_hint}"
        self._draw_text(cr, x, cy - 6, hint, size=14, align="left")

        return False


# --------------------- main ---------------------

def main():
    ap = argparse.ArgumentParser(description="CPU burner + Wayland/GTK monitor with touch controls, CSV logging, and LTC2959 power monitoring")
    ap.add_argument("--interval", type=float, default=0.5, help="UI update interval seconds")
    ap.add_argument("--start-burn", action="store_true", help="Start with burners ON")
    ap.add_argument("--workers", type=int, default=0, help="Initial workers (0=one per visible CPU)")
    ap.add_argument("--log-file", type=str, default=None, help="CSV file path for logging")
    ap.add_argument("--log-auto", action="store_true", help="Start with logging enabled")
    ap.add_argument("--pin-extras", action="store_true",
                    help="Also pin workers beyond CPU count (not recommended; may reduce per-core usage)")
    ap.add_argument("--windowed", action="store_true", help="Run windowed instead of fullscreen")

    args = ap.parse_args()

    win = MonitorUI(interval=args.interval,
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