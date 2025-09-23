# Camera Analysis Suite for Verdin iMX8M Mini

A comprehensive camera testing and analysis suite designed for embedded systems, particularly the Verdin iMX8M Mini with Docker/Weston compositor support. This suite provides both interactive GUI applications and automated analysis tools for USB cameras.

## 🎯 Applications Overview

### **Console Camera Analysis** (Recommended)
- **File**: `console_camera_analysis.py`
- **Best for**: Automated analysis, Docker environments, SSH sessions
- **Features**: Terminal-based UI, real-time progress, Excel report generation
- **Storage**: Saves videos to SD card, keeps successful recordings

### **GTK3 Camera Applications**
- **Files**: `step19_video_recorder.py`, `step20_real_analysis.py`
- **Best for**: Desktop environments with full GUI support
- **Features**: Full GUI interface, real-time video preview
- **Note**: May have issues with Wayland/Docker setups

### **SDL2 Camera Applications** (Experimental)
- **Files**: `sdl2_camera_analysis.py`, `sdl2_safe_camera_analysis.py`
- **Best for**: Lightweight GUI without X11/Wayland dependencies
- **Status**: Experimental, may have compatibility issues

## 🚀 Quick Start

### 1. Install Dependencies

**Complete installation for all applications:**
```bash
apt update && apt install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-gst-1.0 \
    gir1.2-gstapp-1.0 \
    gir1.2-gstvideo-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    v4l-utils \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgtk-3-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    pkg-config \
    build-essential

pip3 install pandas openpyxl pygame
```

**Minimal installation for console app only:**
```bash
apt update && apt install -y \
    python3 \
    python3-pip \
    python3-gi \
    gir1.2-gst-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    v4l-utils

pip3 install pandas openpyxl
```

### 2. Run the Console Camera Analyzer (Recommended)

```bash
python3 console_camera_analysis.py
```

**Interactive menu options:**
1. 📋 Show device summary
2. 🚀 Start complete analysis
3. 🚪 Exit

## 📊 Features

### **Automated Analysis**
- Tests all format/resolution/fps combinations
- Records 15-second samples for each combination
- Measures real bitrates and file sizes
- Generates comprehensive Excel reports
- Color-coded success/failure matrices

### **Real Device Capabilities**
- Uses `v4l2-ctl` to detect actual camera capabilities
- Tests H.264, MJPG, and YUYV formats
- Resolution range: 320x240 to 1920x1080
- Frame rates: 5-30 fps (device dependent)

### **Storage Management**
- **Successful videos**: Saved to SD card (`/var/rootdirs/media/6333-3730`)
- **Failed attempts**: Automatically deleted
- **Excel reports**: Saved to current directory

### **Embedded-Friendly**
- Optimized for dual-core ARM Cortex-A53
- Minimal memory footprint
- Works in Docker containers
- Terminal-based progress display

## 📁 Output Files

### **Excel Report** (`console_camera_analysis.xlsx`)
- **Summary sheet**: Overall statistics
- **Device sheets**: Individual matrices per device/format
- **Color coding**: Green=success, Red=failure
- **Real data**: Measured bitrates and file sizes

### **Video Files** (SD Card: `/var/rootdirs/media/6333-3730`)
- **Naming**: `test_{FORMAT}_{WIDTHxHEIGHT}_{FPS}fps_{TIMESTAMP}.{ext}`
- **Example**: `test_H264_1280x720_30fps_20250923_104835.mp4`
- **Only successful recordings kept**

## 🔧 Camera Device Detection

### Find Available Cameras
```bash
# List video devices
ls /dev/video*

# Show device capabilities
v4l2-ctl --list-devices

# Detailed format information
v4l2-ctl --device=/dev/video0 --list-formats-ext
```

### Test Camera Manually
```bash
# Test H.264 camera
gst-launch-1.0 v4l2src device=/dev/video0 ! video/x-h264,width=1280,height=720,framerate=30/1 ! h264parse ! mp4mux ! filesink location=test.mp4

# Test MJPG camera
gst-launch-1.0 v4l2src device=/dev/video0 ! image/jpeg,width=1280,height=720,framerate=30/1 ! jpegdec ! videoconvert ! autovideosink
```

## 🐳 Docker Usage

### Environment Setup
```bash
# Set display environment
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/tmp/1000-runtime-dir

# Run console analyzer (no GUI needed)
python3 console_camera_analysis.py
```

### Container Requirements
```yaml
# docker-compose.yml
services:
  camera-analyzer:
    volumes:
      - /dev:/dev
      - /var/rootdirs/media/6333-3730:/var/rootdirs/media/6333-3730
      - /tmp/1000-runtime-dir:/tmp/1000-runtime-dir
    environment:
      - WAYLAND_DISPLAY=wayland-0
      - XDG_RUNTIME_DIR=/tmp/1000-runtime-dir
    devices:
      - /dev/video0:/dev/video0
      - /dev/video2:/dev/video2
      - /dev/video4:/dev/video4
    privileged: true
```

## 🛠️ Alternative Applications

### **Step 19: Video Recorder** (`step19_video_recorder.py`)
- **Purpose**: Interactive video recording with GUI
- **Features**: Device selection, format controls, real-time preview
- **Usage**: `python3 step19_video_recorder.py`

### **Step 20: Real Analysis** (`step20_real_analysis.py`)
- **Purpose**: GTK3 version of automated analysis
- **Features**: Full GUI with progress bars and device info
- **Usage**: `python3 step20_real_analysis.py`
- **Note**: May have Wayland compatibility issues

### **SDL2 Versions** (Experimental)
```bash
# Try SDL2 version (if console doesn't work)
python3 sdl2_safe_camera_analysis.py
```

## 🔍 Troubleshooting

### **Camera Issues**
```bash
# Check USB camera detection
lsusb | grep -i camera
dmesg | grep -i video

# Test camera access
v4l2-ctl --device=/dev/video0 --info

# Check permissions
ls -la /dev/video*
sudo usermod -a -G video $USER  # Add user to video group
```

### **GStreamer Issues**
```bash
# Test basic pipeline
gst-launch-1.0 videotestsrc ! autovideosink

# Check plugin availability
gst-inspect-1.0 v4l2src
gst-inspect-1.0 h264parse

# Debug pipeline issues
export GST_DEBUG=3
python3 console_camera_analysis.py
```

### **Storage Issues**
```bash
# Check SD card mount
df -h /var/rootdirs/media/6333-3730

# Check permissions
ls -la /var/rootdirs/media/6333-3730
sudo chmod 777 /var/rootdirs/media/6333-3730  # If needed

# Free up space if needed
rm /var/rootdirs/media/6333-3730/test_*.mp4
```

### **Memory Issues (YUYV Format)**
- **Symptom**: Process gets "Killed" during YUYV recording
- **Cause**: YUYV is uncompressed, uses too much memory/CPU
- **Solution**: Skip YUYV or use lower resolutions only
- **Alternative**: Focus on H.264 and MJPG (more practical anyway)

### **Docker/Wayland Issues**
```bash
# Check Wayland socket
echo $WAYLAND_DISPLAY
ls -la $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY

# Use console app instead of GUI apps in Docker
python3 console_camera_analysis.py  # Works without GUI
```

## 📈 Performance Notes

### **Expected Analysis Time**
- **Total combinations**: ~93 (varies by camera)
- **Time per combination**: 16 seconds
- **Total time**: ~25 minutes for complete analysis
- **Progress**: Real-time progress bar with current test info

### **Hardware Recommendations**
- **RAM**: 1GB+ recommended for YUYV format
- **Storage**: 2GB+ free space on SD card
- **CPU**: Dual-core ARM adequate for H.264/MJPG

### **Format Performance (typical)**
- **H.264**: 500-10,000 kbps, hardware compressed
- **MJPG**: 2,000-45,000 kbps, JPEG compressed
- **YUYV**: Very high bandwidth, often fails on embedded systems

## 🗂️ File Structure

```
Camera/
├── console_camera_analysis.py     # ⭐ Main console analyzer (recommended)
├── step19_video_recorder.py       # GTK3 interactive recorder
├── step20_real_analysis.py        # GTK3 automated analyzer
├── sdl2_camera_analysis.py        # SDL2 version (experimental)
├── sdl2_safe_camera_analysis.py   # Safe SDL2 version
├── camera_analysis.py             # Original analysis tool
├── waylan_camera.py               # Legacy GTK camera viewer
├── README.md                      # This documentation
└── *.py                          # Various development iterations
```

## 🎯 Recommended Workflow

1. **Start with console analyzer**: `python3 console_camera_analysis.py`
2. **Review device summary** to understand capabilities
3. **Run complete analysis** (confirm 25-minute runtime)
4. **Check Excel report** for detailed results
5. **Review saved videos** on SD card for quality assessment
6. **Use step19** for interactive recording if needed

## 🆘 Support

For issues specific to:
- **Verdin iMX8M Mini**: Check Toradex documentation
- **Docker/Weston**: Verify container display setup
- **Camera compatibility**: Test with `v4l2-ctl` and `gst-launch-1.0`
- **Python dependencies**: Use virtual environment if conflicts occur