# Quick Start Guide - Modbus RTU Slave Emulator

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify installation by running tests:**
   ```bash
   python test_emulator.py
   ```
   You should see "ALL TESTS PASSED!"

## Running the Emulator

### Using the GUI Application

```bash
python modbus_rtu_emulator.py
```

This will launch the Windows GUI application where you can:
- Select your RS485 COM port
- Choose baud rate (default: 9600)
- Set number of devices to emulate (1-10)
- Monitor real-time statistics
- View communication logs

### Configuration Steps

1. **Connect your RS485 adapter** to your computer
2. **Launch the application**: `python modbus_rtu_emulator.py`
3. **Select COM port** from the dropdown (e.g., COM3, COM4)
4. **Set baud rate** to match your master device (default: 9600)
5. **Choose number of devices** to emulate (1-10)
6. **Click "Start Emulator"**

The emulator will now respond to Modbus RTU requests as slave devices with addresses 1 through N (where N is the number you selected).

## Example Usage Scenario

**Scenario:** Test a Modbus master that polls 5 slave devices at 9600 baud

1. Set "Num Devices" to 5
2. Set "Baud Rate" to 9600
3. Connect your RS485 adapter to the master device's RS485 bus
4. Click "Start Emulator"
5. Watch the real-time statistics as requests come in

The emulator will respond to requests for devices 1, 2, 3, 4, and 5.

## Monitoring and Statistics

### Real-time Tab
Shows live statistics updated every second:
- Request counts (total, valid, invalid)
- Error counts (CRC, framing, timeout, unsupported functions)
- Bytes transferred
- Per-device request counts
- Function code usage

### Communication Log Tab
Timestamped log of events:
- Emulator start/stop
- Configuration changes
- Error conditions

## Saving Statistics

Click "Save Statistics" to export a timestamped report to a text file. The file will be saved in the current directory as:
```
modbus_stats_YYYYMMDD_HHMMSS.txt
```

## Troubleshooting

### "Failed to open serial port"
- **Cause**: Port is in use or doesn't exist
- **Solution**:
  - Close other applications using the port
  - Click "Refresh" to update COM port list
  - Verify RS485 adapter is connected

### Master device doesn't receive responses
- **Check baud rate**: Must match between master and emulator
- **Check device addresses**: Emulator only responds to addresses 1-10
- **Check wiring**: Verify A/B connections on RS485 bus
- **Check termination**: RS485 bus should have 120Ω termination resistors

### High CRC error rate
- **Check electrical**: Grounding, cable quality, cable length
- **Check interference**: Keep RS485 cables away from power lines
- **Try lower baud rate**: Helps with longer cable runs

## Default Device Memory

Each emulated device has:
- 256 Coils (addresses 0-255, all initially OFF)
- 256 Discrete Inputs (addresses 0-255, all initially OFF)
- 256 Holding Registers (addresses 0-255, all initially 0)
- 256 Input Registers (addresses 0-255, all initially 0)

**Device 1 special values** (matching captured traffic):
- Holding Register 0x0F = 0xE230 (57904 decimal)
- Holding Register 0xF5 = 0x0002
- Holding Register 0xF6 = 0x0004

## Supported Modbus Functions

| Code | Function | Description |
|------|----------|-------------|
| 0x01 | Read Coils | Read 1-2000 coils |
| 0x02 | Read Discrete Inputs | Read 1-2000 discrete inputs |
| 0x03 | Read Holding Registers | Read 1-125 registers |
| 0x04 | Read Input Registers | Read 1-125 registers |
| 0x05 | Write Single Coil | Write one coil |
| 0x06 | Write Single Register | Write one register |
| 0x0F | Write Multiple Coils | Write multiple coils |
| 0x10 | Write Multiple Registers | Write multiple registers |

## Testing Without Hardware

You can test the emulator logic without RS485 hardware:

```bash
python test_emulator.py
```

This runs comprehensive unit tests on:
- CRC-16 calculation and verification
- All supported Modbus functions
- Exception handling
- Device addressing
- Statistics collection

## Advanced Usage

### Programmatic Access

You can use the emulator programmatically in your own Python scripts:

```python
from modbus_rtu_emulator import ModbusRTUEmulator

# Create emulator with 3 devices
emulator = ModbusRTUEmulator(num_devices=3)

# Start on COM3 at 9600 baud
emulator.start(port='COM3', baudrate=9600)

# Let it run...
input("Press Enter to stop...")

# Stop and print statistics
emulator.stop()
print(emulator.stats.get_summary())
```

### Customizing Device Memory

Modify device memory before starting:

```python
from modbus_rtu_emulator import ModbusRTUEmulator

emulator = ModbusRTUEmulator(num_devices=1)

# Set specific register values
emulator.devices[1].holding_registers[100] = 0x1234
emulator.devices[1].coils[50] = True

# Start emulator
emulator.start(port='COM3', baudrate=9600)
```

## Tips for Best Results

1. **Match baud rates** between master and emulator exactly
2. **Use proper RS485 wiring**: Twisted pair cable, proper termination
3. **Keep cables short** when testing at high baud rates
4. **Monitor statistics** to catch communication issues early
5. **Save statistics** before stopping for analysis
6. **Start with 1 device** then increase to test multiple slaves

## Next Steps

For detailed information, see the full [README.md](README.md).
