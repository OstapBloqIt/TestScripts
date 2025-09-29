 System Configuration Profile: iMX8M Mini Verdin SoM Development Environment

  Hardware Platform

  - SoM: iMX8M Mini Verdin on carrier board
  - Display: 800x1280 portrait MIPI-DSI with DSI-LVDS bridge
  - Input: Touch interface (no mouse/keyboard available)
  - Architecture: ARM64 (aarch64)

  Operating System & Display Stack

  - OS: Torizon Core 6.8.1 (Debian-based container OS)
  - Kernel: Linux 5.15.148-6.8.1-devel+git.1cbf48124747
  - Display Server: Weston compositor (Wayland)
  - Environment: Docker container with user torizon (uid 1000), running as root

  Critical GPU Driver Limitations

  ⚠️ MAJOR CONSTRAINT: iMX Vivante GPU drivers (imx-gpu-viv-wayland) have specific incompatibilities:

  Incompatible Technologies

  - ❌ SDL2: Bus errors on any rendering operations (even basic rectangles)
  - ❌ OpenGL/EGL development headers: Package conflicts - missing libegl-dev, libgl-dev
  - ❌ Direct framebuffer access: Invisible due to Weston compositor control
  - ❌ Hardware-accelerated rendering with SDL2: Causes segmentation faults and bus errors

  Working Graphics Solutions

  - ✅ GTK3 applications: Work perfectly with the existing system
  - ✅ Web-based applications: HTML/CSS/JavaScript in Chromium browser
  - ✅ Chromium with specific flags:
  DISPLAY=:0 chromium --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --disable-software-rasterizer --disable-features=VizDisplayCompositor \
  --kiosk --use-fake-ui-for-media-stream
  - ✅ Terminal/console applications: Text-based interfaces work fine

  Development Environment Details

  Container Environment

  Working directory: /home/torizon/simple_SDL2
  Platform: linux
  OS Version: Linux 5.15.148-6.8.1-devel+git.1cbf48124747
  Is directory a git repo: No

  Available Tools

  - ✅ Compilers: gcc, standard C development tools
  - ✅ Python 3: Available for HTTP servers, scripting
  - ✅ Chromium browser: Full WebRTC and modern web API support
  - ✅ Package management: apt (with specific GPU driver conflicts for OpenGL/EGL dev packages)
  - ✅ GTK3: Fully functional for native GUI applications

  Network Configuration

  - Localhost HTTP servers: Work perfectly (127.0.0.1)
  - Python HTTP server: python3 -m http.server 8000 for web app serving
  - Touch input devices: /dev/input/event0-4 available

  Key Discoveries & Workarounds

  Graphics Application Strategy

  ❌ Don't attempt: SDL2-based applications (bus errors with GPU drivers)
  ✅ Recommended approaches:
  - GTK3 native applications
  - Web-based applications served via HTTP to Chromium
  - Terminal/console applications

  Display Management

  ❌ Don't attempt: Direct framebuffer writing (invisible due to Weston)
  ✅ Working approaches:
  - GTK3 applications with Wayland
  - Chromium kiosk mode with HTML/CSS for fullscreen web apps

  Development Package Constraints

  - OpenGL/EGL development headers: Blocked by iMX GPU driver conflicts
  - SDL2 development: Installs but runtime failures due to GPU driver issues
  - GTK3 development: Fully available and functional

  Recommended Application Architectures

  Option 1: Native GTK3 Application

  # Install GTK3 development
  apt install libgtk-3-dev

  # Compile GTK3 application
  gcc app.c -o app `pkg-config --cflags --libs gtk+-3.0`

  Option 2: Web-based Application

  # Backend: Simple HTTP server
  python3 -m http.server 8000 --bind 127.0.0.1 &

  # Frontend: Launch fullscreen web application
  DISPLAY=:0 chromium --kiosk --no-sandbox --disable-dev-shm-usage \
  --disable-gpu --use-fake-ui-for-media-stream http://127.0.0.1:8000/app.html &

  Sample Working Configuration Commands

  # For web applications
  python3 -m http.server 8000 --bind 127.0.0.1 &
  DISPLAY=:0 chromium --kiosk --no-sandbox --disable-dev-shm-usage \
  --disable-gpu --disable-software-rasterizer --disable-features=VizDisplayCompositor \
  --no-first-run --disable-infobars --disable-session-crashed-bubble \
  --disable-component-extensions-with-background-pages \
  --use-fake-ui-for-media-stream http://127.0.0.1:8000/app.html &

  # For GTK3 applications
  DISPLAY=:0 ./gtk_app

  Important Constraints for Future Projects

  - SDL2 framework unusable - causes bus errors with iMX GPU drivers
  - Portrait orientation display - design for 800x1280 touch interface
  - OpenGL/EGL development headers unavailable - package conflicts with GPU drivers
  - Container environment - limited system access, no systemctl
  - Touch-first interface - no mouse/keyboard input available
  - GTK3 fully supported - recommended for native GUI applications

  Preferred Development Approaches (in order)

  1. GTK3 native applications - Full system integration, native performance
  2. Web-based applications - Cross-platform, rich UI capabilities, easy development
  3. Terminal/console applications - Always reliable, no graphics constraints

  This configuration represents a GTK3 + web-capable embedded development environment where SDL2 is the primary limitation, but both native GTK3
   and modern web technologies provide full hardware access and professional UI capabilities.