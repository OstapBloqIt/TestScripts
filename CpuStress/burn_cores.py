#!/usr/bin/env python3
# Max out all available CPU cores until stopped.
# Works on Linux (incl. Torizon containers). No external deps.

import argparse
import math
import os
import signal
import sys
import time
from glob import glob
from multiprocessing import Process, Event, current_process

# ---------- Helpers ----------
def online_cpus():
    # Respect cgroup/affinity limits if present
    try:
        return sorted(os.sched_getaffinity(0))
    except AttributeError:
        # Fallback
        cnt = os.cpu_count() or 1
        return list(range(cnt))

def set_affinity(cpu_id):
    try:
        os.sched_setaffinity(0, {cpu_id})
    except Exception:
        pass  # Inside some containers this might be blocked; ignore.

def burn_loop(stop_evt):
    # Mixed int + FP hot loop to keep cores busy and DVFS honest.
    x = 1.0001
    y = 123456789
    while not stop_evt.is_set():
        # Do a bunch of fused operations per iteration.
        x = x * 1.0000003 + math.sqrt(x) - math.log(x)
        y = (y * 1664525 + 1013904223) & 0xFFFFFFFF
        # Prevent overly predictable pipelines; touch both int and float paths.
        if (y & 0xFF) == 0:
            x = x % 1000.0
        # Keep variables live so nothing gets optimized away (Python won't anyway).
        if x < 0:  # never true, but keeps 'x' used
            break

def find_thermal_sensors():
    """Return list of (name, path_to_temp) for CPU/SOC thermal zones."""
    sensors = []
    for tz in sorted(glob("/sys/class/thermal/thermal_zone*")):
        try:
            tname = open(os.path.join(tz, "type"), "r").read().strip()
        except Exception:
            continue
        lname = tname.lower()
        if "cpu" in lname or "soc" in lname:
            tpath = os.path.join(tz, "temp")
            if os.path.exists(tpath):
                sensors.append((tname, tpath))
    return sensors

def read_temp_milli_c(path):
    try:
        v = int(open(path, "r").read().strip())
        return v  # usually millidegrees C
    except Exception:
        return None

def cpu_freq_paths():
    """Return list of (cpuN, path_to_scaling_cur_freq) that exist."""
    paths = []
    for cdir in sorted(glob("/sys/devices/system/cpu/cpu[0-9]*")):
        f = os.path.join(cdir, "cpufreq", "scaling_cur_freq")
        if os.path.exists(f):
            cpu = os.path.basename(cdir)
            paths.append((cpu, f))
    return paths

def read_freq_khz(path):
    try:
        v = int(open(path, "r").read().strip())
        return v  # kHz
    except Exception:
        return None

# ---------- Monitor ----------
def monitor_loop(stop_evt, log_path=None, interval=1.0, print_status=True):
    sensors = find_thermal_sensors()
    freqs = cpu_freq_paths()
    header_printed = False
    f = None

    if log_path:
        f = open(log_path, "w", buffering=1)
        cols = ["ts"]
        cols += [f"temp_{name}_mC" for name, _ in sensors]
        cols += [f"{cpu}_kHz" for cpu, _ in freqs]
        f.write(",".join(cols) + "\n")

    while not stop_evt.is_set():
        ts = time.time()
        temps = [read_temp_milli_c(p) for _, p in sensors]
        curfreqs = [read_freq_khz(p) for _, p in freqs]

        if f:
            row = [f"{ts:.3f}"]
            row += [str(v) if v is not None else "" for v in temps]
            row += [str(v) if v is not None else "" for v in curfreqs]
            f.write(",".join(row) + "\n")

        if print_status:
            if not header_printed:
                print("Monitoring temps/freqs each {:.1f}s (Ctrl+C to stop)".format(interval), flush=True)
                header_printed = True
            s1 = " | ".join(
                f"{name}={t/1000:.1f}°C" if t is not None else f"{name}=?"
                for name, (_, t) in zip([n for n, _ in sensors], enumerate(temps))
            )
            s2 = " ".join(
                f"{cpu}={khz/1000 if khz else '?'}MHz" for cpu, khz in zip([c for c, _ in freqs], curfreqs)
            )
            if s1 or s2:
                print(f"[{time.strftime('%H:%M:%S')}] {s1}   {s2}", flush=True)

        time.sleep(interval)

    if f:
        f.close()

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Peg all CPU cores for thermal/load testing.")
    ap.add_argument("--workers", type=int, default=0, help="Number of worker processes. Default: one per available CPU.")
    ap.add_argument("--no-affinity", action="store_true", help="Do not pin workers to specific CPUs.")
    ap.add_argument("--log", type=str, default="", help="CSV file to log temps/frequencies. Optional.")
    ap.add_argument("--interval", type=float, default=1.0, help="Logging/print interval seconds. Default 1.0")
    ap.add_argument("--quiet", action="store_true", help="Do not print live monitor lines.")
    args = ap.parse_args()

    cpus = online_cpus()
    if args.workers > 0:
        nworkers = args.workers
    else:
        nworkers = max(1, len(cpus))

    stop_evt = Event()

    # Graceful shutdown on Ctrl+C / SIGTERM
    def handle_sig(signum, frame):
        print("\nSignal received, stopping workers...", flush=True)
        stop_evt.set()
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    print(f"Detected CPUs available: {len(cpus)} -> starting {nworkers} workers", flush=True)

    procs = []
    for i in range(nworkers):
        def target(idx=i):
            if not args.no_affinity:
                # Bind to a CPU in round-robin across available set
                target_cpu = cpus[idx % len(cpus)]
                set_affinity(target_cpu)
            burn_loop(stop_evt)

        p = Process(target=target, name=f"burner-{i}", daemon=False)
        p.start()
        procs.append(p)

    # Monitoring in the main process
    try:
        monitor_loop(stop_evt, log_path=args.log if args.log else None,
                     interval=args.interval, print_status=(not args.quiet))
    finally:
        stop_evt.set()
        for p in procs:
            p.join(timeout=2.0)

    print("All workers stopped.", flush=True)

if __name__ == "__main__":
    main()

