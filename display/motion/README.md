# Wayland Test Pattern (GTK3 + Cairo) for TorizonOS

Fullscreen moving test patterns with FPS overlay, designed to run *inside* a container that can talk to the Weston compositor on TorizonOS.

This repo contains a single script:
- wayland_pattern.py — draws RGB bars, checkerboard, gradients, or solid fills, with smooth motion and an FPS overlay.

---

## Features

- Wayland-native via GTK3/GDK
- Cairo rendering
- Smooth animation with target FPS
- FPS overlay box (top-left)
- Multiple patterns: bars, checker, gradient, solid colors

---

## Requirements

You need a running Weston compositor on the device (typically the standard TorizonOS Weston container).
The runner container (where you execute the script) needs:

- Python 3
- GTK3 introspection bindings
- PyGObject and Cairo bindings

Debian packages (install in your runner container):

    apt-get update && apt-get install -y \
    python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 && \
    apt-get clean

---

## How it connects to Weston (Wayland socket)

Weston exposes a Wayland socket under /tmp/1000-runtime-dir/wayland-0 by default on Torizon.
To render, your runner container must:

1) Mount /tmp from the host (so you can see the Wayland socket).
2) Set:
   - XDG_RUNTIME_DIR=/tmp/1000-runtime-dir
   - WAYLAND_DISPLAY=wayland-0
   - GDK_BACKEND=wayland
3) Ideally run as the same UID that owns the socket (usually UID 1000 on Torizon).

---

## Quick Start (run inside a helper container)

From your device (where Weston is already running in another container):

# 1) Clone your repo (or copy the script) onto the device
git clone <your-repo-url> /home/torizon/pattern && cd /home/torizon/pattern

# 2) Start a transient container with the needed deps and Wayland access
docker run --rm -it \
  --name pattern-runner \
  --device /dev/dri \
  -v /tmp:/tmp \
  -v "$PWD":/app \
  -w /app \
  -e XDG_RUNTIME_DIR=/tmp/1000-runtime-dir \
  -e WAYLAND_DISPLAY=wayland-0 \
  -e GDK_BACKEND=wayland \
  --user 1000:1000 \
  debian:bookworm-slim bash

# 3) Inside the container shell, install deps and run the script
apt-get update && apt-get install -y \
  python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 && apt-get clean

python3 ./wayland_pattern.py --pattern bars --speed 160 --fps 60

If your Weston uses a different runtime dir or display name, adjust XDG_RUNTIME_DIR and WAYLAND_DISPLAY accordingly.

---

## Option B: Build a tiny image for repeated use

Create a Dockerfile in the repo:

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
  python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 && \
  apt-get clean

WORKDIR /app
COPY wayland_pattern.py /app/wayland_pattern.py

ENV GDK_BACKEND=wayland
CMD ["python3", "/app/wayland_pattern.py", "--pattern", "bars", "--speed", "160", "--fps", "60"]

Build and run:

docker build -t torizon-pattern:latest .
docker run --rm -it \
  --device /dev/dri \
  -v /tmp:/tmp \
  -e XDG_RUNTIME_DIR=/tmp/1000-runtime-dir \
  -e WAYLAND_DISPLAY=wayland-0 \
  --user 1000:1000 \
  torizon-pattern:latest

---

## CLI Usage

python3 wayland_pattern.py [--pattern {bars,checker,gradient,solid-red,solid-green,solid-blue}] \
                           [--speed FLOAT] \
                           [--fps INT] \
                           [--font NAME] \
                           [--font-size PX]

- --pattern    Pattern to render. Defaults to bars.
- --speed      Motion speed in pixels per second. Default 120.0.
- --fps        Target frame rate limiter. Default 60.
- --font       Font family for FPS overlay. Default monospace.
- --font-size  FPS overlay text size in px. Default 24.

Example:
XDG_RUNTIME_DIR=/tmp/1000-runtime-dir WAYLAND_DISPLAY=wayland-0 GDK_BACKEND=wayland \
python3 wayland_pattern.py --pattern gradient --speed 200 --fps 90

---

## Troubleshooting

- "TypeError: Couldn't find foreign struct converter for 'cairo.Context'"
  Install both python3-cairo and python3-gi-cairo inside the runner container.

- Black screen or nothing draws
  Check that -v /tmp:/tmp is mounted and XDG_RUNTIME_DIR points to the correct directory that contains wayland-0.
  Verify ls -l /tmp/1000-runtime-dir/wayland-0 inside the runner container.

- Permission denied on Wayland socket
  Run the container as the same UID as the Weston user (typically --user 1000:1000).

- "No protocol specified" or GTK falls back
  Ensure GDK_BACKEND=wayland is set. If the target board only offers Wayland, X11 won’t work.

- Slow/tearing
  Lower --fps or --speed. Confirm the device GPU/DRM node is passed via --device /dev/dri.

---

## Development Notes

- The script forces Wayland backend via Gdk.set_allowed_backends("wayland").
- The gradient uses a repeating Cairo pattern for seamless wrap.
- The checkerboard snaps cell edges to integers to avoid blurry antialiasing.

---

## License

Choose and fill in a license (MIT/BSD/Apache-2.0). Add a LICENSE file accordingly.
