# Touch Test Utilities for TorizonOS (Docker + Weston/Wayland)

This repo contains two Python tools for validating touch input on devices running **TorizonOS**, with graphics handled by a **Weston** Wayland compositor running in a Docker container:

- `touch_tester.py` — high-level GTK/Wayland touch visualizer (no direct `/dev/input` access).
- `evdev_touch_tester.py` — raw evdev visualizer/diagnostic that reads `/dev/input/event*` directly and maps raw coordinates to screen space.

Both tools render an on-screen trail for touches, basic HUD info, and optional CSV logging.

---

## Quick start

You need an existing **Weston** container running (the standard Torizon Wayland stack). These tools run in a **separate** app container that shares the Wayland socket and, for the evdev tool, the input devices.

### 1) Build an app image

Use a Wayland-capable base with GTK3, Cairo, and PyGObject. Example `Dockerfile`:

```dockerfile
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
