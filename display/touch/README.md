# Touch Test Utilities for TorizonOS (Docker + Weston/Wayland)

This repo contains two Python tools for validating touch input on devices running TorizonOS, with graphics handled by a Weston Wayland compositor running in a Docker container:

- touch_tester.py — high-level GTK/Wayland touch visualizer (no direct /dev/input access).
- evdev_touch_tester.py — raw evdev visualizer/diagnostic that reads /dev/input/event* directly and maps raw coordinates to screen space.

Both tools render on-screen trails for touches, provide a small HUD, and support optional CSV logging.

--------------------------------------------------------------------------------

## Quick start

You need an existing Weston container running (the standard Torizon Wayland stack). These tools run in a separate app container that shares the Wayland socket and, for the evdev tool, the input devices.

### 1) Build an app image

Use a Wayland-capable base with GTK3, Cairo, and PyGObject. Example Dockerfile:

    FROM torizon/wayland-base:latest

    # System deps
    RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        python3-gi gir1.2-gtk-3.0 \
        python3-cairo \
        python3-evdev \
        && rm -rf /var/lib/apt/lists/*

    WORKDIR /app
    COPY touch_tester.py evdev_touch_tester.py /app/

    # Default command shows help
    CMD ["python3", "/app/touch_tester.py", "--help"]

Build it on your dev machine:

    docker build -t touch-test:latest .

### 2) Run with the Weston socket mounted

Weston typically exposes a Wayland socket at /tmp/1000-runtime-dir/wayland-0. Mount that into the app container and set the env variables so GTK can find it.

    WAYLAND_DIR=/tmp/1000-runtime-dir
    WAYLAND_SOCK=wayland-0

    docker run --rm -it \
      -e XDG_RUNTIME_DIR=$WAYLAND_DIR \
      -e WAYLAND_DISPLAY=$WAYLAND_SOCK \
      -v $WAYLAND_DIR:$WAYLAND_DIR \
      touch-test:latest \
      python3 /app/touch_tester.py --fullscreen

If you see a blank screen or a “cannot connect to display” error, verify:
- The Weston container is running and has created $WAYLAND_DIR/$WAYLAND_SOCK
- The path is mounted into this app container
- The user inside the app container can access the socket (root inside the container is simplest)

### 3) Raw evdev mode (optional, deeper diagnostics)

To read the touchscreen directly via evdev, you must also pass input devices into the container.

Find your touchscreen event node on the host (TorizonOS):

    ls -l /dev/input/event*
    evtest /dev/input/eventX

Then run:

    EVENT_DEV=/dev/input/event2   # example; change to your device

    docker run --rm -it \
      --privileged \
      -e XDG_RUNTIME_DIR=$WAYLAND_DIR \
      -e WAYLAND_DISPLAY=$WAYLAND_SOCK \
      -v $WAYLAND_DIR:$WAYLAND_DIR \
      --device $EVENT_DEV \
      --device /dev/dri/card0 --device /dev/dri/renderD128 \
      touch-test:latest \
      python3 /app/evdev_touch_tester.py --device $EVENT_DEV --fullscreen --log /tmp/touch_evdev.csv

Alternative (pass the entire /dev/input tree):

    docker run --rm -it \
      --privileged \
      -e XDG_RUNTIME_DIR=$WAYLAND_DIR \
      -e WAYLAND_DISPLAY=$WAYLAND_SOCK \
      -v $WAYLAND_DIR:$WAYLAND_DIR \
      -v /dev/input:/dev/input \
      --device /dev/dri/card0 --device /dev/dri/renderD128 \
      touch-test:latest \
      python3 /app/evdev_touch_tester.py --device /dev/input/event2

--------------------------------------------------------------------------------

## Docker Compose example

docker-compose.yaml:

    services:
      touch-test:
        image: touch-test:latest
        environment:
          - XDG_RUNTIME_DIR=/tmp/1000-runtime-dir
          - WAYLAND_DISPLAY=wayland-0
        volumes:
          - /tmp/1000-runtime-dir:/tmp/1000-runtime-dir
          # Option A: entire input dir
          - /dev/input:/dev/input
        devices:
          # Option B: explicit devices instead of volume mapping
          - /dev/dri/card0
          - /dev/dri/renderD128
        privileged: true
        command: ["python3", "/app/touch_tester.py", "--fullscreen"]

Bring it up:

    docker compose up --build

--------------------------------------------------------------------------------

## Usage

### touch_tester.py (GTK/Wayland)

Run:

    python3 /app/touch_tester.py [--fullscreen] [--log /path/to/file.csv]

Keyboard:

- Esc: quit
- F: toggle fullscreen
- G: toggle grid
- E: toggle edge coverage bands
- T: toggle tap targets
- P: toggle pinch HUD
- C: clear trails/stats
- L: toggle CSV logging

CSV columns:

    timestamp_ms,event,seq_id,x,y,pressure

### evdev_touch_tester.py (raw evdev)

Run:

    python3 /app/evdev_touch_tester.py --device /dev/input/event2 \
      [--grab] [--fullscreen] [--log /path/to/file.csv] \
      [--swap-xy] [--invert-x] [--invert-y] [--rotate {0,90cw,90ccw,180}]

Keyboard:

- Esc: quit
- F: toggle fullscreen
- G: toggle grid
- L: toggle CSV logging
- C: clear trails
- X: swap X/Y
- I: invert X
- K: invert Y

CSV columns:

    ts_ms,ev,slot,tid,x_raw,y_raw,x_px,y_px,pressure,maj,min

--------------------------------------------------------------------------------

## Persisting logs

Mount a host directory to capture CSVs:

    mkdir -p ./logs
    docker run --rm -it \
      -e XDG_RUNTIME_DIR=$WAYLAND_DIR -e WAYLAND_DISPLAY=$WAYLAND_SOCK \
      -v $WAYLAND_DIR:$WAYLAND_DIR \
      -v $(pwd)/logs:/logs \
      touch-test:latest \
      python3 /app/touch_tester.py --log /logs/touch.csv

--------------------------------------------------------------------------------

## Troubleshooting

- “Couldn’t connect to Wayland display”
  - Confirm Weston is running and the socket path is correct.
  - Ensure -v /tmp/1000-runtime-dir:/tmp/1000-runtime-dir and the env vars are set.

- GTK/Cairo import errors like “Couldn’t find foreign struct converter for 'cairo.Context'”
  - Make sure python3-gi, gir1.2-gtk-3.0, and python3-cairo are installed in the image.
apt-get update
apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-cairo


- No input shows up in evdev tool
  - Verify the correct /dev/input/eventX.
  - Pass the device node(s) into the container and use --privileged if needed.
  - Some devices require exclusive grab (--grab) to report events.

- Coordinates mapped wrong / rotated
  - Use --rotate 90cw/90ccw/180, --swap-xy, and axis inversion flags to align touch to display.

- Rendering permissions / DRM access
  - If /dev/dri access fails, switch to --privileged, or explicitly pass card and render nodes:
    --device /dev/dri/card0 --device /dev/dri/renderD128

--------------------------------------------------------------------------------

## License

MIT. See LICENSE.
