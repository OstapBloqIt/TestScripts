# USB Camera Touch Viewer for Verdin iMX8M Mini

A touch-enabled camera application designed for the Verdin iMX8M Mini with Wayland compositor support. Features real-time video display with comprehensive touch controls for resolution, frame rate, and system monitoring.

## Features
- **Touch-First Interface**: Optimized for touchscreen interaction with large buttons and intuitive controls
- **Resolution Control**: Support for resolutions from 320x240 to 1920x1080
- **Frame Rate Adjustment**: Variable frame rate from 0-60 fps with real-time slider control
- **System Monitoring**: Live CPU and memory usage display
- **Full-Screen Display**: Automatic fullscreen mode for immersive viewing
- **Wayland Compatible**: Native support for Wayland compositor with fallback rendering

## System Requirements
- Verdin iMX8M Mini (or compatible ARM/x86 Linux system)
- USB camera (UVC compatible)
- Wayland compositor (Weston recommended)
- Display with MIPI-DSI output and DSI-LVDS bridge support
- Touchscreen input device

## Dependencies Installation

### Ubuntu/Debian Systems

```bash
# Update package list
sudo apt update

# Install Python 3 and pip
sudo apt install python3 python3-pip

# Install GTK4 and GObject Introspection
sudo apt install libgtk-4-1 libgtk-4-dev gobject-introspection libgirepository1.0-dev

# Install GStreamer and plugins
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly

# Install GStreamer development libraries
sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev

# Install Video4Linux utilities (optional, for camera testing)
sudo apt install v4l-utils

# Install Python GI bindings
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-gstreamer-1.0

# For OpenCV-based testing (camera.py)
sudo apt install python3-opencv
```

### Additional Dependencies for ARM/Embedded Systems

```bash
# GPU drivers and Wayland support
sudo apt install mesa-utils-extra libwayland-egl1 libwayland-client0 libwayland-server0

# Hardware acceleration support
sudo apt install gstreamer1.0-vaapi gstreamer1.0-libav
```

## Usage

### Running the Touch Camera Application

```bash
python3 waylan_camera.py
```

### Environment Variables

- `CAM_DEVICE`: Specify camera device (default: `/dev/video0`)
  ```bash
  CAM_DEVICE=/dev/video1 python3 waylan_camera.py
  ```

### Controls

- **Resolution Dropdown**: Select from predefined resolutions (320x240 to 1920x1080)
- **FPS Slider**: Adjust frame rate from 0-60 fps
- **Pause/Play Button**: Toggle video stream
- **Apply Button**: Apply resolution/fps changes
- **Exit Button**: Close application
- **Resource Monitor**: Real-time CPU and memory usage display

## Camera Device Detection

To find available camera devices:

```bash
# List video devices
ls /dev/video*

# Get camera capabilities
v4l2-ctl --list-devices
v4l2-ctl --device=/dev/video0 --list-formats-ext
```

## Troubleshooting

### Camera Not Detected
```bash
# Check if camera is recognized
lsusb | grep -i camera
dmesg | grep -i video
```

### GStreamer Issues
```bash
# Test GStreamer pipeline manually
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink

# Check available GStreamer plugins
gst-inspect-1.0 | grep v4l2
```

### Permission Issues
```bash
# Add user to video group
sudo usermod -a -G video $USER
# Logout and login again
```

### Wayland Display Issues
```bash
# Ensure Wayland socket is available
echo $WAYLAND_DISPLAY
ls -la $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY
```

## Docker/Container Usage

If running in a container, ensure these mounts and permissions:

```yaml
# docker-compose.yml example
services:
  camera-app:
    volumes:
      - /dev/video0:/dev/video0
      - /run/user/1000:/run/user/1000
    environment:
      - WAYLAND_DISPLAY=wayland-0
      - XDG_RUNTIME_DIR=/run/user/1000
    devices:
      - /dev/video0:/dev/video0
    privileged: true
```

## File Structure

- `waylan_camera.py` - Main touch-enabled camera application
- `camera.py` - Simple OpenCV camera test script
- `README.md` - This documentation

## Hardware Notes

- Tested on Verdin iMX8M Mini with Weston compositor
- Supports MIPI-DSI displays via DSI-LVDS bridge
- UVC-compatible USB cameras recommended
- Touch input automatically detected by GTK4

## Performance Optimization

- Uses Cairo renderer fallback for stability on embedded GPUs
- Hardware-accelerated video decode when available
- Efficient CPU/memory monitoring with minimal overhead
- Optimized for ARM Cortex-A53 architecture
