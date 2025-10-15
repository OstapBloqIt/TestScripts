# Modbus RTU Slave Emulator

A comprehensive Windows application for emulating Modbus RTU slave devices on RS485 half-duplex communication bus.

## Features

- **Multi-Device Emulation**: Emulate 1-10 Modbus slave devices simultaneously (addresses 1-10)
- **Full Modbus RTU Support**: Implements standard Modbus function codes:
  - 0x01: Read Coils
  - 0x02: Read Discrete Inputs
  - 0x03: Read Holding Registers
  - 0x04: Read Input Registers
  - 0x05: Write Single Coil
  - 0x06: Write Single Register
  - 0x0F: Write Multiple Coils
  - 0x10: Write Multiple Registers
- **Error Detection**: Comprehensive error detection and logging:
  - CRC-16 validation errors
  - Framing errors
  - Timeout errors
  - Unsupported function codes
- **Real-time Statistics**: Live monitoring of:
  - Total/valid/invalid requests
  - Per-device request counts
  - Function code usage
  - Bytes sent/received
  - Error counts by type
- **Communication Log**: Timestamped event logging
- **Half-Duplex RS485**: Proper timing for half-duplex communication
- **Windows GUI**: Easy-to-use graphical interface

## Installation

### Prerequisites
- Python 3.7 or higher
- Windows OS

### Install Dependencies
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Emulator

1. **Run the application**:
   ```bash
   python modbus_rtu_emulator.py
   ```

2. **Configure settings**:
   - Select COM port from dropdown
   - Choose baud rate (9600, 19200, 38400, 57600, 115200)
   - Set number of devices to emulate (1-10)

3. **Start emulation**:
   - Click "Start Emulator"
   - The emulator will begin responding to Modbus requests

### Using the GUI

**Configuration Panel**:
- **COM Port**: Select your RS485 adapter's COM port
- **Baud Rate**: Match your master device's baud rate
- **Num Devices**: Number of slave devices to emulate

**Status Display**:
- Shows current state (Running/Stopped)
- Displays port, baud rate, and device count

**Statistics Tab**:
- Real-time statistics updated every second
- Shows request counts, errors, and data transfer
- Per-device and per-function-code breakdowns

**Communication Log Tab**:
- Timestamped event log
- Shows emulator start/stop events
- Records errors and important events

**Action Buttons**:
- **Clear Log**: Clear the communication log
- **Save Statistics**: Export statistics to timestamped text file
- **Reset Statistics**: Reset all counters to zero

### Device Memory Map

Each emulated device has:
- **256 Coils** (read/write bits, addresses 0-255)
- **256 Discrete Inputs** (read-only bits, addresses 0-255)
- **256 Holding Registers** (read/write 16-bit, addresses 0-255)
- **256 Input Registers** (read-only 16-bit, addresses 0-255)

Device 1 has pre-configured values matching the captured traffic:
- Holding Register 0x0F = 0xE230 (57904)
- Holding Register 0xF5 = 0x0002
- Holding Register 0xF6 = 0x0004

## Statistics Output

The emulator tracks comprehensive statistics:

```
MODBUS RTU SLAVE EMULATOR - STATISTICS
============================================================
Runtime: 120.5 seconds

REQUESTS:
  Total Requests:     1523
  Valid Requests:     1518
  Invalid Requests:   5
  Responses Sent:     1518

ERRORS:
  CRC Errors:         3
  Framing Errors:     2
  Timeout Errors:     0
  Unsupported Func:   0

DATA TRANSFER:
  Bytes Received:     10661
  Bytes Sent:         8844

PER-DEVICE REQUESTS:
  Device 01:        758
  Device 02:        760

FUNCTION CODE USAGE:
  Read Coils           : 1200
  Read Holding Registers: 318
============================================================
```

## Technical Details

### CRC-16 Calculation
- Uses Modbus RTU standard CRC-16 algorithm
- Polynomial: 0xA001
- Initial value: 0xFFFF
- Low-byte first order

### Frame Detection
- Uses 3.5 character time for frame separation
- 10ms timeout at 9600 baud (scales with baud rate)

### Half-Duplex Timing
- 2ms response delay after receiving request
- Prevents bus collisions

### Serial Port Settings
- Data bits: 8
- Parity: None
- Stop bits: 1
- Flow control: None

## Troubleshooting

**"Failed to open serial port"**:
- Ensure COM port is not in use by another application
- Check that RS485 adapter is properly connected
- Verify correct COM port number

**No responses received by master**:
- Verify baud rate matches master device
- Check RS485 wiring (A/B polarity)
- Ensure device addresses match (1-10 for emulator)
- Check that termination resistors are present

**CRC Errors**:
- Check for electrical noise on RS485 bus
- Verify proper grounding
- Check cable quality and length

**High error rates**:
- Reduce baud rate for long cables
- Add termination resistors (120Ω) at both ends
- Check for electromagnetic interference

## Example Use Cases

1. **Development Testing**: Test Modbus master applications without physical hardware
2. **Protocol Validation**: Verify correct Modbus RTU implementation
3. **Load Testing**: Test with multiple devices simultaneously
4. **Training**: Learn Modbus protocol without expensive equipment
5. **Debugging**: Isolate issues by comparing with known-good slave

## License

This software is provided as-is for testing and development purposes.

## Support

For issues or questions, refer to the project documentation or contact the development team.
