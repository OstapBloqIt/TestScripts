# How to Use

## Running the Script

Run the script with:

```bash
python3 burn_cores.py
```

This will:

- Launch one worker per available CPU
- Pin each worker to a core
- Print temperatures and frequencies (if the kernel exposes them)

To stop the script, press `Ctrl+C`. The workers will exit cleanly.

## Optional Logging

You can log output to a CSV file for later graphing:

```bash
python3 burn_cores.py --log imx8mm_quad.csv
```

For a dual-core board:

```bash
python3 burn_cores.py --log imx8mm_dual.csv
```

Notes:

- If your container or kernel hides CPU frequency or thermal zones, logging will skip those fields without errors.
- To silence live prints, use `--quiet`.
- To disable CPU pinning, use `--no-affinity`. By default, each worker is bound to a specific core to avoid scheduler conflicts.

## Notes for Your Benchmark Setup

- Ensure DVFS/governor settings are consistent across boards, or your test may simply reflect which board throttles first.
- Inside a container, the visible CPUs might be limited by cpusets. The script will respect whatever CPUs it can see.
- Use a heatsink, fan, or at least a martyr’s patience. The i.MX8M Mini will throttle when it gets hot—this is expected behavior during testing.

# Running the GUI Version

## Run it on your Verdin under Weston

Inside your Weston container (if needed):

```bash
export XDG_RUNTIME_DIR=/tmp/1000-runtime-dir
export WAYLAND_DISPLAY=wayland-0
```

Then run:

```bash
python3 burn_cores_gui.py --fullscreen --start-burn --interval 0.3
```

## What You Get

- Big, readable per-CPU bars with heat coloring from green → red as utilization climbs
- Temperature bars for CPU/SOC sensors that go red as the silicon heats up
- Live load averages and current worker count
- Controls:
  - `Space` → Toggle the burn without closing the overlay  
  - `+ / -` → Adjust the number of workers  
  - `Esc` → Quit

## Notes

- If your container is missing **`python3-gi`**, **`gir1.2-gtk-3.0`**, **`python3-gi-cairo`** or **`python3-cairo`**, install them in the image.
- If your thermal or `cpufreq` sysfs isn’t exposed, those fields will just show **“n/a”** instead of crashing.

---

There: pretty graphs while you set the Mini on fire.  
(But try not to annihilate the poor dual-core just to feel something.)

