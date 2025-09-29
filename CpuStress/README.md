# i.MX8M Mini CPU Stress Test + LTC2959 Power Monitor

A comprehensive CPU stress testing and power monitoring application for i.MX8M Mini systems with integrated LTC2959IDDBTRMPBF power measurement chip support.

## Features

### 🔥 CPU Stress Testing
- **Multi-core CPU burning** - Stress test individual CPU cores
- **Dynamic worker control** - Add/remove workers on the fly
- **Core affinity pinning** - Pin workers to specific CPU cores
- **Real-time CPU usage monitoring** - Per-core and overall CPU utilization
- **CPU frequency monitoring** - Track scaling frequencies per core

### ⚡ LTC2959 Power Monitoring
- **Real-time power measurements** - Voltage, current, and power consumption
- **Accurate readings** - Uses LTC2959IDDBTRMPBF I2C power monitor (bus 3, address 0x63)
- **Continuous sampling** - 1250 samples/sec alternating V+I measurements
- **10mΩ sense resistor support** - Optimized for high-current applications
- **VDD voltage input** - Monitors ~12V system supply

### 🌡️ Thermal Monitoring
- **Multiple temperature sensors** - Automatic detection of thermal zones
- **Real-time temperature display** - Color-coded temperature bars
- **CPU/SoC sensor prioritization** - Focus on relevant thermal data

### 📊 Data Logging & Visualization
- **CSV logging** - Comprehensive data export including power measurements
- **Real-time GUI** - GTK3/Cairo-based touch-friendly interface
- **Load average tracking** - System load monitoring
- **Fullscreen/windowed modes** - Flexible display options

### 📱 Touch Controls
- **[Burn ON/OFF]** - Toggle CPU stress testing
- **[−] / [+]** - Decrease/increase worker count
- **[Quit]** - Exit application
- **[REC ●/○]** - Toggle CSV logging

## Hardware Requirements

### System
- **i.MX8M Mini** based board
- **Linux** with Wayland/X11 support
- **Python 3.8+** with GTK3 bindings

### Power Monitoring (Optional)
- **LTC2959IDDBTRMPBF** power monitor chip
- **I2C bus 3, address 0x63**
- **10mΩ current sense resistor** (RES CURRENT SENSE .010 OHM 1W 1%)
- **~12V VDD supply monitoring**

## Installation

### Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-gi python3-cairo
sudo apt install gir1.2-gtk-3.0 python3-smbus

# Install Python dependencies
pip3 install --user argparse
```

### Permissions
```bash
# Add user to i2c group for LTC2959 access
sudo usermod -a -G i2c $USER
# Logout and login again for group changes to take effect
```

## Usage

### Basic GUI Application (Recommended)
```bash
# Run with power monitoring in windowed mode
python3 burn_cores_gui_power.py --windowed

# Start with CPU burning enabled
python3 burn_cores_gui_power.py --start-burn --windowed

# Start with automatic CSV logging
python3 burn_cores_gui_power.py --log-auto --windowed

# Fullscreen mode (default)
python3 burn_cores_gui_power.py --log-auto
```

### Command Line Interface (Legacy)
```bash
# Basic CPU stress test
python3 burn_cores.py

# With CSV logging
python3 burn_cores.py --log cpu_stress_test.csv

# Quiet mode
python3 burn_cores.py --quiet --log results.csv
```

### Command Line Options (GUI)
```bash
python3 burn_cores_gui_power.py [OPTIONS]

Options:
  --interval FLOAT      UI update interval in seconds (default: 0.5)
  --start-burn         Start with CPU burners ON
  --workers INT        Initial number of workers (default: CPU count)
  --log-file PATH      Custom CSV file path for logging
  --log-auto           Start with logging enabled
  --pin-extras         Pin extra workers beyond CPU count (not recommended)
  --windowed           Run in windowed mode (default: fullscreen)
  -h, --help           Show help message
```

### Examples
```bash
# Start stress test with power monitoring and logging
python3 burn_cores_gui_power.py --start-burn --log-auto --windowed

# High-frequency monitoring for detailed analysis
python3 burn_cores_gui_power.py --interval 0.25 --log-file detailed_analysis.csv --windowed

# Start with 2 workers for partial load testing
python3 burn_cores_gui_power.py --workers 2 --start-burn --windowed
```

## Power Monitor Configuration

The application automatically detects and configures the LTC2959IDDBTRMPBF power monitor:

### LTC2959 Specifications
- **I2C Address:** 0x63 on bus 3
- **Voltage Range:** 1.8V to 60V (monitoring VDD ~12V)
- **Current Range:** ±97.5mV across sense resistor
- **Sense Resistor:** 10mΩ (0.010Ω, 1W, 1%)
- **Sample Rate:** 1250 samples/sec alternating V+I
- **Resolution:** 16-bit ADC

### Automatic Configuration
The LTC2959 is automatically configured on startup:
```
ADC Control Register B: 0x80
- Bits [7:5] = 100: Continuous V+I alternating mode
- Bit [2] = 0: Use VDD as voltage input
- Power calculation: P = V × I (more accurate than power register)
```

## CSV Data Format

When logging is enabled, comprehensive CSV files are generated:

### Standard Columns
```
timestamp_iso, timestamp_ms, overall_cpu_pct, load1, load5, load15,
burning, workers, cpu0_pct, cpu1_pct, cpu2_pct, cpu3_pct,
freq0_khz, freq1_khz, freq2_khz, freq3_khz,
temp0_c, temp1_c, voltage_v, current_a, power_w,
voltage_raw, current_raw, power_raw
```

### Example Data
```csv
2024-01-15T14:32:45.123,1705325565123,87,1.25,0.98,0.76,1,4,95,89,82,78,1800000,1800000,1800000,1800000,45.2,47.1,12.456,0.623,7.756,13048,63347,62946
```

## GUI Interface

### Display Areas
1. **Header** - Application title and LTC2959 status
2. **Status Line** - Load average, burn status, worker count
3. **Overall CPU Bar** - System-wide CPU utilization
4. **LTC2959 Power Section** - Real-time measurements
5. **Per-CPU Bars** - Individual core utilization + frequencies
6. **Temperature Sensors** - Color-coded thermal monitoring
7. **Control Bar** - Touch-friendly buttons

### Power Monitor Display
```
LTC2959 Power Monitor:
Voltage: 12.456 V
Current: 0.623 A
Power: 7.756 W

Raw V: 0x3308 (13064)
Raw I: 0xF7D9 (63449)
Raw P: 0xF5EA (62954)
```

### Controls
- **Touch/Click** - All buttons are touch-friendly
- **[Burn ON/OFF]** - Toggle CPU stress testing
- **[−] / [+]** - Adjust worker count during stress test
- **[Quit]** - Exit application safely
- **[REC ●/○]** - Toggle CSV logging on/off

## Troubleshooting

### Power Monitor Issues

#### LTC2959 not detected
```bash
# Check I2C bus and device
sudo i2cdetect -y 3
# Should show device at address 0x63: 63

# Check I2C permissions
ls -l /dev/i2c-3
# Should be readable/writable by i2c group

# Add user to i2c group
sudo usermod -a -G i2c $USER
# Logout and login for changes to take effect
```

#### Incorrect current readings
- **Verify 10mΩ sense resistor value** - Application is calibrated for 0.010Ω
- **Check connections** - Ensure proper I2C wiring to LTC2959
- **Power supply** - Confirm ~12V VDD input voltage
- **Compare with multimeter** - Cross-check readings

### Software Issues

#### SMBus not available
```bash
# Install SMBus Python library
sudo apt install python3-smbus
```

#### GTK/Cairo errors
```bash
# Install required GUI libraries
sudo apt install python3-gi python3-cairo gir1.2-gtk-3.0
```

#### Application won't start
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Check dependencies
python3 -c "import gi; print('GTK OK')"
python3 -c "from smbus import SMBus; print('SMBus OK')"
```

## Hardware Integration

### LTC2959 Connection Diagram
```
LTC2959IDDBTRMPBF Pin Configuration:
Pin 1  (VDD)    → 3.3V supply + 100nF bypass capacitor
Pin 2  (SENSEP) → High side of 10mΩ current sense resistor
Pin 3  (CFP)    → 470nF filter capacitor
Pin 4  (CFN)    → 470nF filter capacitor
Pin 5  (SENSEN) → Low side of 10mΩ current sense resistor
Pin 6  (SCL)    → I2C clock (bus 3)
Pin 7  (SDA)    → I2C data (bus 3)
Pin 8  (GPIO)   → Not connected
Pin 9  (VREG)   → 1µF bypass to GND
Pin 10 (GND)    → System ground
```

### Current Sense Resistor Placement
```
[12V Supply] ──┬── [10mΩ Resistor] ──┬── [i.MX8M Mini Load]
                │                     │
                │  ┌─────────────┐   │
                └──┤2 SENSEP     │   │
                   │  LTC2959    │   │
                   │5 SENSEN     ├───┘
                   │  0x63       │
                   │I2C Bus 3    │
                   └─────────────┘
```

## File Structure

```
CpuStress/
├── burn_cores_gui_power.py    # Main GUI application with LTC2959
├── burn_cores.py              # Legacy CLI stress tester
├── burn_cores_gui.py          # Legacy GUI without power monitoring
├── test_*.py                  # LTC2959 test scripts
├── ltc2959.pdf               # LTC2959 datasheet
└── README.md                 # This file
```

### Key Classes
- **LTC2959PowerMonitor** - I2C power measurement interface
- **BurnerManager** - Multi-process CPU stress testing
- **CpuStatReader** - CPU utilization monitoring
- **CsvLogger** - Data logging with power measurements
- **MonitorUI** - GTK3 GUI with touch controls

## Performance Validation

### Expected Results
With properly functioning LTC2959 power monitoring:

**Idle System:**
- CPU: 5-15% utilization
- Power: 2-4W consumption
- Current: 0.2-0.4A draw
- Temperature: <50°C

**Full Load (4 workers):**
- CPU: 95-100% per core
- Power: 6-12W consumption
- Current: 0.5-1.0A draw
- Temperature: 60-85°C (thermal throttling)

### Benchmarking Tips
- **Consistent DVFS settings** across test runs
- **Adequate cooling** to prevent thermal throttling
- **Stable power supply** for accurate measurements
- **Multiple test runs** for statistical validity

## Development

### Adding Custom Sensors
```python
# Add new power monitor in LTC2959PowerMonitor.__init__()
self.custom_sensor = CustomSensor(bus=3, address=0x64)

# Update read_all_measurements() method
def read_all_measurements(self):
    # ... existing code ...
    custom_data = self.custom_sensor.read()
    return {**standard_data, 'custom': custom_data}
```

### Extending CSV Format
```python
# Update CsvLogger fieldnames in __init__()
fieldnames += ["custom_sensor_v", "custom_value"]

# Update log() method data writing
row["custom_sensor_v"] = custom_data.get('voltage', '')
```

## Contributing

1. **Fork** the repository
2. **Create** feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** changes (`git commit -m 'Add amazing feature'`)
4. **Push** to branch (`git push origin feature/amazing-feature`)
5. **Open** Pull Request

### Development Guidelines
- Follow existing code style and structure
- Test with and without LTC2959 hardware
- Update CSV format documentation for new fields
- Ensure backward compatibility with legacy versions

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **Analog Devices** - LTC2959 power monitor datasheet and specifications
- **NXP Semiconductors** - i.MX8M Mini processor documentation
- **GTK Project** - GUI toolkit and Cairo graphics library
- **Python Community** - SMBus I2C library and related tools

---

**⚡ Monitor your i.MX8M Mini's performance and power consumption with precision! ⚡**