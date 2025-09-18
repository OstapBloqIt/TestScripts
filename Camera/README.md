# Wayland Touch Camera Viewer for Verdin i.MX8M Mini

A touch‑first USB camera viewer designed for embedded Linux (Toradex Verdin i.MX8M Mini) running in a Docker container with a Weston Wayland compositor. The app provides an on‑screen interface to view, control, and monitor a USB camera.

## Features
- **Touch controls only** (no keyboard required)
- **Resolution presets**: from 320×240 up to 1920×1080
- **Frame rate control**: 0–60 fps (0 pauses the stream)
- **On‑screen controls**: play/pause, apply settings, exit
- **Live resource monitor**: CPU and RAM usage
- **Wayland‑native rendering** using GTK4 + GStreamer `gtksink`

## Requirements
Make sure the following are available inside the container:
- Python 3
- `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-gst-1.0`
- GStreamer: `gstreamer1.0-plugins-base`, `gstreamer1.0-plugins-good`, `gstreamer1.0-plugins-bad`, (`gstreamer1.0-libav` optional)
- `v4l-utils` (optional, for camera info)

## Files
- `touch_cam.py`: Main application
- `Dockerfile`: Build instructions for the container
- `docker-compose.yml`: Example service configuration

## Building
```bash
docker build -t touch-cam .
```

## Running
Run the container with access to the Wayland socket and your USB camera device:

```bash
docker run --rm \
  -e WAYLAND_DISPLAY=wayland-0 \
  -e CAM_DEVICE=/dev/video0 \
  -v /tmp/wayland-0:/tmp/wayland-0 \
  --device /dev/video0 \
  touch-cam
```

Or use `docker-compose`:
```yaml
services:
  touch-cam:
    build: .
    environment:
      - WAYLAND_DISPLAY=wayland-0
      - CAM_DEVICE=/dev/video0
    devices:
      - "/dev/video0:/dev/video0"
    volumes:
      - "/tmp/wayland-0:/tmp/wayland-0"
    network_mode: "host"
    ipc: "host"
    restart: unless-stopped
```
Run with:
```bash
docker compose up --build
```

## Usage
- Select resolution from the dropdown.
- Adjust frame rate with the slider.
- Press **Apply** to restart the pipeline with new settings.
- Use **Pause/Play** to toggle streaming.
- **Exit** closes the app.
- CPU and RAM usage are displayed in real time.

## Notes
- The app defaults to `/dev/video0`. Override with `CAM_DEVICE` environment variable.
- If `gtksink` is missing, it will fall back to `autovideosink` (not embeddable inside the UI).
- Some cameras may only support MJPG/YUYV at specific resolutions. If needed, add decoders into the pipeline.

## License
MIT License
