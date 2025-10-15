# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This repository contains automated validation tools for USB enumeration, CP2104/CP2108 UART devices, and RS485 transceivers on the Toradex Verdin iMX8M Mini SoM platform running Torizon Core.

## Hardware Context

**Platform**: Toradex Verdin iMX8M Mini SoM on custom carrier board (CB2v4)
**Operating System**: Torizon Core 6.8.1 (Debian-based container system)
**Kernel**: Linux 5.15.148-6.8.1-devel

### USB Topology
```
iMX8M Mini USB Bus 2 (ci_hdrc.1)
└── Microchip USB Hub (0424:2517) - 7-port hub at 2-1
    ├── Port 5: CP2108 Quad UART Bridge (10c4:ea71) at 2-1.5
    │   ├── Interface 0 → ttyUSB0 (RS485 Channel 0)
    │   ├── Interface 1 → ttyUSB1 (RS485 Channel 1)
    │   ├── Interface 2 → ttyUSB2 (RS485 Channel 2)
    │   └── Interface 3 → ttyUSB3 (RS485 Channel 3)
    └── Port 1: CP2104 (10c4:ea60) at 2-1.1 [Known issue: connection unstable]
```

## Running Validation

### Basic Usage
```bash
# Run with timestamped output filename
./usb_rs485_validator.sh

# Run with custom output filename
./usb_rs485_validator.sh my_custom_report.md
```

### What Gets Validated
- USB device enumeration and topology
- CP2108 Quad UART Bridge presence and interface mapping
- CP2104 single UART device detection
- RS485 transceiver channels (4 channels via CP2108)
- USB hub configuration and port status
- Kernel driver loading and binding (cp210x module)
- Serial device node creation (/dev/ttyUSB0-3)

### Output Format
- **Console**: Color-coded summary with pass/fail status
- **Markdown Report**: Comprehensive validation report with topology diagrams, device details, interface mappings, and recommendations

## Architecture

### Validation Script Structure (`usb_rs485_validator.sh`)

**Data Collection Functions (lines 57-110)**
- `collect_all_data()`: Orchestrates system data collection
  - USB device enumeration via `lsusb` and `lsusb -t`
  - Detailed device info via `lsusb -v` for specific VID:PID
  - Kernel messages via `dmesg` filtering for cp210x and USB bus 2
  - Serial device discovery via sysfs (`/sys/class/tty/ttyUSB*`)
  - CP2108 interface inspection via sysfs (`/sys/bus/usb/devices/2-1.5:1.*`)
  - Driver status via `lsmod` and `modinfo`
  - Stores all data in temporary files under `/tmp/usb_validation_$$`

**Report Generation (lines 116-495)**
- `generate_report()`: Analyzes collected data and generates markdown report
  - Parses device presence (CP2108, CP2104, USB hub)
  - Counts operational RS485 channels (ttyUSB0-3)
  - Detects CP2104 disconnection scenarios (previously seen but now missing)
  - Generates comprehensive markdown with:
    - Executive summary with status icons
    - USB topology tree
    - Device-specific validation sections
    - Interface mapping tables
    - Pass/fail results table
    - Actionable recommendations

**Main Execution Flow (lines 501-546)**
- Create temporary directory for data collection
- Collect all system data via `collect_all_data()`
- Analyze and generate report via `generate_report()`
- Display console summary with color-coded status
- Clean up temporary files on exit (via trap)

### Critical USB Device Paths
- **CP2108 sysfs path**: `/sys/bus/usb/devices/2-1.5/`
- **CP2108 interfaces**: `/sys/bus/usb/devices/2-1.5:1.{0,1,2,3}/`
- **CP2104 sysfs path**: `/sys/bus/usb/devices/2-1.1/` (when connected)
- **USB hub path**: `/sys/bus/usb/devices/2-1/`
- **Serial device nodes**: `/dev/ttyUSB0` through `/dev/ttyUSB3` (RS485 channels)

### Key Device Identifiers
- **USB Hub**: VID `0424`, PID `2517` (Microchip)
- **CP2108**: VID `10c4`, PID `ea71` (Silicon Labs Quad UART)
- **CP2104**: VID `10c4`, PID `ea60` (Silicon Labs Single UART)
- **Kernel Driver**: `cp210x` module (handles both CP2108 and CP2104)

## Known Issues & Limitations

### CP2104 Connection Instability
The CP2104 device at USB hub port 1 exhibits intermittent connection issues:
- Device enumerates briefly then disconnects within ~1 second
- Kernel detects it as `ttyUSB8` before disconnect
- Likely a physical connection or power delivery issue
- Validation script detects both current status and historical detection

### Safe Device Inspection
**WARNING**: Do NOT use `ls /dev/ttyUSB*` directly - it can crash SSH sessions on this platform.
Use sysfs inspection methods instead:
```bash
ls -la /sys/class/tty/ttyUSB*              # Safe method
find /sys/bus/usb-serial/devices/ -type l  # Alternative safe method
```

### Other Serial Devices
Note that ttyUSB4-7 are used by the Quectel EC25 LTE modem on USB Bus 1 (separate from the RS485 channels). The validation script focuses on RS485 channels (ttyUSB0-3) from the CP2108.

## Development Constraints

### Graphics Stack Limitations
This system runs in a Torizon container with Weston/Wayland compositor:
- **DO NOT use SDL2** - completely broken, causes bus errors and system crashes
- OpenGL/EGL development headers unavailable (conflicts with imx-gpu-viv-wayland)
- Direct framebuffer access (`/dev/fb0`) exists but not visible (Weston controls display)
- **Use GTK3** for native GUI applications (`apt install libgtk-3-dev`)
- **Use web apps** (HTML/CSS/JS + Chromium kiosk mode) for complex UIs

### Display Configuration
- Resolution: 800x1280 portrait orientation
- Touch-only input (no mouse/keyboard)
- Display variable: `DISPLAY=:0`

### Container Environment
- Running as root in Docker container
- Limited systemctl access (container environment, not full system)
- Package manager: apt (Debian packages)

## Modifying the Validation Script

### Adding New Device Checks
1. Add device-specific data collection in `collect_all_data()` (save to `$TEMP_DIR`)
2. Add analysis logic in `generate_report()` (parse temporary files)
3. Add report sections with status icons (✅/❌/⚠️)
4. Update validation summary table
5. Add recommendations for new failure modes

### Changing USB Paths
If hardware topology changes (e.g., CP2108 moves to different hub port):
- Update hardcoded USB device paths (currently `2-1.5` for CP2108, `2-1.1` for CP2104)
- Update sysfs inspection paths in lines 90-94, 106-109
- Update interface detection logic in lines 143-147, 258-264, 332-338
- Update device path documentation in report generation

### Report Format Changes
The script generates GitHub-flavored markdown with:
- Tables for structured data
- Code blocks (triple backticks) for command output
- Status icons (✅/❌/⚠️) for visual feedback
- Hierarchical sections (##, ###) for organization
- Follow existing conventions when adding new sections

## Troubleshooting Commands

```bash
# Check USB enumeration
lsusb                           # List all USB devices
lsusb -t                        # Show USB device tree with drivers
lsusb -v -d 10c4:ea71          # CP2108 detailed info
lsusb -v -d 10c4:ea60          # CP2104 detailed info

# Inspect kernel messages
dmesg | grep -i cp210          # CP210x driver messages
dmesg | grep "usb 2-"          # USB Bus 2 messages
dmesg | tail -50               # Recent kernel messages

# Check driver status
lsmod | grep cp210x            # Check if cp210x module loaded
modinfo cp210x                 # Display cp210x module info

# Inspect serial devices (SAFE methods)
ls -la /sys/class/tty/ttyUSB*
find /sys/bus/usb-serial/devices/ -type l

# Check CP2108 interfaces via sysfs
cat /sys/bus/usb/devices/2-1.5/product
cat /sys/bus/usb/devices/2-1.5/serial
ls /sys/bus/usb/devices/2-1.5:1.*/
```

## Additional Documentation

- **SYSTEM_DESCRIPTION.txt**: Comprehensive hardware and software documentation including full USB topology, all peripherals, graphics stack details, and platform-specific constraints
- **README.md**: User-facing documentation for running validation tools and interpreting results
- **USB_RS485_Validation_Report.md**: Example baseline validation report showing expected output format
