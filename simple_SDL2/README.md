# SDL2 Application for iMX8M Mini with Weston

## Overview
This project successfully implements SDL2 applications on an iMX8M Mini Verdin SoM with MIPI-DSI display, running Torizon Core 6.8.1 with Weston compositor.

## Key Findings

### Working Configuration
- **Video Driver**: Wayland (automatically selected by SDL2)
- **Display**: 800x1280@57Hz detected correctly
- **Renderer**: OpenGL with iMX Vivante GPU acceleration
- **Compilation**: Manual header extraction due to package conflicts with `imx-gpu-viv-wayland`

### iMX-Specific Challenges Resolved
1. **Package Conflicts**: Standard `libsdl2-dev` conflicts with `imx-gpu-viv-wayland` drivers
2. **Solution**: Manual header extraction and custom compilation flags
3. **Video Driver**: SDL2 correctly auto-selects Wayland over KMS/DRM (which would conflict with Weston)

## Files
- `sdl2_test.c` - Diagnostic application with detailed driver information
- `sdl2_app.c` - Production-ready animated application
- `Makefile` - Build system with proper iMX flags

## Build & Run
```bash
make clean && make
./sdl2_app
```

## Compilation Details
- **Headers**: Manually installed to `/usr/local/include/SDL2/`
- **Libraries**: Link against existing SDL2 runtime (`libSDL2-2.0.so.0`)
- **Flags**: `-I/usr/local/include -L/usr/lib/aarch64-linux-gnu -lSDL2 -lm`

## Verified Features
✅ Wayland integration with Weston compositor
✅ iMX Vivante GPU acceleration (OpenGL ES)
✅ MIPI-DSI display detection and rendering
✅ Window creation and event handling
✅ Smooth animation and color rendering

## Environment
- Platform: iMX8M Mini Verdin SoM
- OS: Torizon Core 6.8.1
- Compositor: Weston 10.0.1 (DRM backend)
- Display: MIPI-DSI with DSI-LVDS bridge
- Container: Docker with Wayland socket access