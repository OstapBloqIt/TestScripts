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

