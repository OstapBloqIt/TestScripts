# Touchscreen Test UI + Logger (TorizonOS + Docker)

Fullscreen touch diagnostics for Linux/Wayland devices running TorizonOS. Renders visual targets and live trails for each finger, reports per-slot sampling rate and jitter, and optionally logs events to CSV.

* **Display stack:** Wayland client (SDL2 via Pygame) connecting to a running Weston compositor.
* **Input:** reads multitouch events directly from `/dev/input/eventX` via `python-evdev`.
* **Logging:** optional CSV of `down`, `move`, `up` events.

## Repo contents

* `test_touch.py` — Pygame UI + evdev reader, auto-detects a multitouch device when `--device` is not given.
* `run-local.sh` — convenience wrapper to run the tester for a specific `/dev/input/event*` and write a CSV log.
* `log.csv` — example output (schema described below).

## What you need on the device

1. **TorizonCore** running Weston (host or a separate "weston" container). You should already have a Wayland socket at something like:

   * `XDG_RUNTIME_DIR=/tmp/1000-runtime-dir`
   * `WAYLAND_DISPLAY=wayland-0`
2. **Docker** available on the device.
3. Access to:

   * the Wayland socket directory (`$XDG_RUNTIME_DIR`)
   * the input devices (`/dev/input/event*`)
   * the GPU DRM node (`/dev/dri`) for hardware-accelerated rendering

## Building a container image

Create a minimal image with Python, Pygame and evdev. Example `Dockerfile`:

```dockerfile
# Base: Torizon Debian with Wayland libs. Choose the tag that matches your BSP.
FROM torizon/wayland-base:3

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3 python3-pip python3-evdev python3-pygame \
      libdrm2 libwayland-client0 ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# SDL/Pygame uses Wayland automatically when available.
ENV XDG_RUNTIME_DIR=/tmp/1000-runtime-dir \
    WAYLAND_DISPLAY=wayland-0 \
    SDL_VIDEODRIVER=wayland

ENTRYPOINT ["/bin/bash"]
```

Build it on the device:

```bash
docker build -t touch-tester:latest .
```

> If your board uses a different Torizon base (e.g., Vivante-specific images), switch the base image accordingly.

## Running the tester container

You must bind-mount the Wayland socket directory and input devices, and pass through the DRM device:

```bash
docker run --rm -it \
  -e XDG_RUNTIME_DIR=/tmp/1000-runtime-dir \
  -e WAYLAND_DISPLAY=wayland-0 \
  -v /tmp/1000-runtime-dir:/tmp/1000-runtime-dir \
  --device /dev/dri \
  -v /dev/input:/dev/input:ro \
  -v $(pwd):/app \
  -w /app \
  touch-tester:latest \
  ./run-local.sh /dev/input/event2 /tmp/touch_log.csv
```

Notes:

* Replace `/dev/input/event2` with the correct touchscreen node (see **Finding your input device** below).
* You can also run the Python script directly to use auto-detect:

  ```bash
  docker run --rm -it \
    -e XDG_RUNTIME_DIR=/tmp/1000-runtime-dir \
    -e WAYLAND_DISPLAY=wayland-0 \
    -v /tmp/1000-runtime-dir:/tmp/1000-runtime-dir \
    --device /dev/dri \
    -v /dev/input:/dev/input:ro \
    -v $(pwd):/app -w /app \
    touch-tester:latest \
    python3 test_touch.py --log /tmp/touch_log.csv
  ```

### Finding your input device

On the host:

```bash
evtest       # list devices and their capabilities
# or
ls -l /dev/input/by-path/
```

Pick the `eventX` that corresponds to your touchscreen (usually reports `ABS_MT_POSITION_X`/`Y`).

## On-screen UI and controls

* Fullscreen test view with five targets: `center`, `top`, `bottom`, `left`, `right`.
* Per-finger trails drawn in different colors.
* HUD at top-left shows:

  * Device name and evdev node
  * ABS resolution ranges
  * For each active slot: sampling rate (Hz) and interval jitter (ms)
  * Tap verdicts (PASS/FAIL) for accuracy to the nearest target
* **Quit:** press `Esc` or `q` on a connected keyboard.

## CSV logging

Enable logging by passing `--log path.csv` or by using `run-local.sh` which sets it for you. The CSV columns are:

```
ts, slot, tracking_id, x, y, type
```

* `ts` — monotonic timestamp (seconds)
* `slot` — MT slot index
* `tracking_id` — evdev tracking id for a contact, or empty when none yet
* `x`, `y` — screen-space pixel coordinates
* `type` — `down`, `move`, `up`

## Typical problems and fixes

* **Black screen or no window:** confirm Weston is running and the Wayland socket is mounted in the container. Validate `ls $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY` inside the container.
* **Permission denied on `/dev/input/eventX`:** run container as root (default) and ensure the device is mounted read-only into the container.
* **Low FPS or stutter:** make sure `/dev/dri` is passed to the container; verify you’re using a Wayland base image with GPU drivers for your SoC.
* **Touches appear in a corner:** verify that the events being read are from the correct touchscreen and that the device reports `ABS_MT_POSITION_X/Y`. Try a different `eventX` and re-run.

## Development notes

* The script can auto-detect a suitable MT device if `--device` is not provided.
* The jitter threshold and pass/fail messages are for quick field checks; tune in code as needed.
* To change accuracy tolerance, use `--tolerance N` (pixels).

## License

Put your project’s license here. If omitted, the default is “all rights reserved.”
