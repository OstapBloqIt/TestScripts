# Modbus RTU Emulator V3 - CU48 Protocol

## Overview

Version 3 is specifically designed for the **CU48 lock controller protocol**, emulating up to 10 CU48 devices on a Windows RS485 serial port. Each device controls 48 individual electronic locks.

## Key Features

### CU48-Specific Features
- **48 Locks per Device**: Each CU48 device controls 48 locks (addresses 0x00-0x2F / 0-47)
- **Default State**: All locks initialize as CLOSED/LOCKED (coil value = 1)
- **Real-time Lock Control**: GUI interface to manually control individual locks
- **Lock Operation Tracking**: Statistics for lock/unlock operations
- **Protocol Compliant**: Fully implements CU48 Modbus RTU protocol

### From V2 (Inherited)
- Detailed error tracking with last 5 errors
- Error position highlighting in frames
- CRC mismatch detection with expected vs actual values
- Frame analysis and decoding

### From V1 (Inherited)
- 1-based device addressing (devices 1-10, addresses 0x01-0x0A)
- Multi-device emulation (1-10 devices)
- RS485 half-duplex communication
- Comprehensive statistics tracking
- Windows GUI application

## CU48 Protocol Specifications

### Lock Status
- **Coil Value 1** (True) = Door CLOSED/LOCKED
- **Coil Value 0** (False) = Door UNLOCKED/OPEN
- **Status Representation**: 48 bits = 6 bytes

### Default Baud Rate
- **115200** baud (configurable via GUI)

### Supported Modbus Functions
1. **0x01 - Read Coils**: Read lock status (all 48 locks)
2. **0x03 - Read Holding Registers**: Read configuration
3. **0x05 - Write Single Coil**: Unlock/lock single door
4. **0x06 - Write Single Register**: Write configuration
5. **0x0F - Write Multiple Coils**: Unlock/lock multiple doors
6. **0x10 - Write Multiple Registers**: Write multiple configurations

### Lock Addressing
- **Lock #1** = Coil address 0x00 (0 decimal)
- **Lock #48** = Coil address 0x2F (47 decimal)

## GUI Features

### Lock Control Tab (New in V3!)
- **Visual Lock Grid**: 48 lock indicators arranged in 8x6 grid
- **Color Coding**:
  - **Green** = CLOSED/LOCKED (1)
  - **Red** = UNLOCKED (0)
- **Click to Toggle**: Manually control individual locks
- **Device Selector**: Switch between devices 1-10
- **Quick Actions**:
  - **Close All Locks**: Set all 48 locks to CLOSED
  - **Unlock All Locks**: Set all 48 locks to UNLOCKED

### Other Tabs
- **Statistics**: Real-time statistics including lock operations
- **Last 5 Errors**: Detailed error analysis with frame highlighting
- **Communication Log**: Timestamped event log

## Usage

### Starting the Emulator

1. **Launch the Application**:
```bash
python modbus_rtu_emulator_v3.py
```

2. **Configure Settings**:
   - Select COM port (RS485 adapter)
   - Set baud rate (default: 115200 for CU48)
   - Choose number of devices (1-10)

3. **Start Emulating**:
   - Click "Start Emulator"
   - All devices start with 48 locks CLOSED

### Manual Lock Control

1. Go to "Lock Control (CU48)" tab
2. Select device (1-10) using spinner
3. Click any lock button to toggle its state
4. Or use "Close All Locks" / "Unlock All Locks" buttons

### Testing with Modbus Master

#### Example 1: Read All 48 Lock Stati
```
Request:  01 01 00 00 00 30 [CRC]
          │  │  └─┬──┘ └─┬─┘
          │  │    │      └── Count: 48 (0x30)
          │  │    └───────── Start address: 0
          │  └────────────── Function: Read Coils
          └───────────────── Device address: 1

Response: 01 01 06 FF FF FF FF FF FF [CRC]
          │  │  │  └────────┬────────┘
          │  │  │           └────────── 48 bits (6 bytes) - all FF = all closed
          │  │  └───────────────────── Byte count: 6
          │  └──────────────────────── Function: Read Coils
          └─────────────────────────── Device address: 1
```

#### Example 2: Unlock Lock #1
```
Request:  01 05 00 00 00 00 [CRC]
          │  │  └─┬──┘ └─┬─┘
          │  │    │      └── Value: 0x0000 = Unlock
          │  │    └───────── Lock address: 0 (Lock #1)
          │  └────────────── Function: Write Single Coil
          └───────────────── Device address: 1

Response: 01 05 00 00 00 00 [CRC]  (Echo back)
```

#### Example 3: Lock Lock #1
```
Request:  01 05 00 00 FF 00 [CRC]
          │  │  └─┬──┘ └─┬─┘
          │  │    │      └── Value: 0xFF00 = Lock/Close
          │  │    └───────── Lock address: 0 (Lock #1)
          │  └────────────── Function: Write Single Coil
          └───────────────── Device address: 1

Response: 01 05 00 00 FF 00 [CRC]  (Echo back)
```

#### Example 4: Unlock Multiple Locks (Locks #1-8)
```
Request:  01 0F 00 00 00 08 01 00 [CRC]
          │  │  └─┬──┘ └─┬─┘ │  └─ Values: 0x00 = all unlocked
          │  │    │      │    └──── Byte count: 1
          │  │    │      └───────── Count: 8 locks
          │  │    └──────────────── Start address: 0
          │  └───────────────────── Function: Write Multiple Coils
          └──────────────────────── Device address: 1

Response: 01 0F 00 00 00 08 [CRC]
          (Echo back start address and count)
```

## Statistics

V3 tracks CU48-specific statistics:

```
CU48 LOCK OPERATIONS:
  Locks Unlocked:     25
  Locks Locked:       12
```

Plus all standard Modbus statistics:
- Total/Valid/Invalid requests
- CRC/Framing/Timeout errors
- Per-device request counts
- Function code usage
- Data transfer (bytes sent/received)

## Files

- **modbus_rtu_emulator_v3.py**: Main application with GUI
- **test_emulator_v3.py**: Comprehensive test suite
- **CU48_V3_README.md**: This documentation

## Testing

Run the automated test suite:

```bash
python test_emulator_v3.py
```

Expected output:
```
======================================================================
ALL V3 CU48 TESTS PASSED!
======================================================================

V3 CU48 Features Verified:
  ✓ 48 locks per device (addresses 0x00-0x2F)
  ✓ All locks initialize as CLOSED/LOCKED (1)
  ✓ Read coil status returns all 48 lock states
  ✓ Write single coil to unlock/lock individual locks
  ✓ Write multiple coils to unlock/lock multiple locks
  ✓ Lock state changes tracked in statistics
  ✓ Multiple CU48 devices supported
  ✓ Boundary condition checking
  ✓ Full CU48 protocol compliance
```

## Technical Details

### CU48Device Class
- Inherits from ModbusSlaveDevice concept
- 48 locks stored as boolean array (True = closed, False = unlocked)
- All locks initialize to `True` (CLOSED)
- Enforces 48-lock boundary (addresses 0-47)

### Lock Status Encoding
48 bits packed into 6 bytes, LSB first:
```
Byte 0: Locks 1-8   (bits 0-7)
Byte 1: Locks 9-16  (bits 0-7)
Byte 2: Locks 17-24 (bits 0-7)
Byte 3: Locks 25-32 (bits 0-7)
Byte 4: Locks 33-40 (bits 0-7)
Byte 5: Locks 41-48 (bits 0-7)
```

Each bit: 1 = closed/locked, 0 = unlocked/open

### Exception Handling
Returns proper Modbus exception responses for:
- **0x02**: Illegal data address (beyond lock 48)
- **0x03**: Illegal data value (invalid coil value)
- **0x01**: Illegal function (unsupported function code)

## Differences from V2

| Feature | V2 | V3 (CU48) |
|---------|----|-----------
| Device Addressing | 0-based (0-9) | **1-based (1-10)** |
| Lock Count | Generic 256 coils | **48 locks (CU48)** |
| Default State | All coils = 0 | **All locks = 1 (CLOSED)** |
| GUI Lock Control | None | **48-lock visual grid** |
| Lock Statistics | None | **Unlock/lock counters** |
| Default Baud | 9600 | **115200 (CU48)** |
| Boundary Checks | 256 coils | **48 locks enforced** |
| Protocol | Generic Modbus | **CU48-specific** |

## Version History

- **V3**: CU48 protocol support with 48-lock control
- **V2**: Enhanced error tracking and analysis
- **V1**: Basic multi-device Modbus RTU emulation

## Requirements

- Python 3.7+
- pyserial
- tkinter (usually included with Python)
- Windows OS
- RS485 USB adapter

## License

This tool is for testing and development purposes.

## Author

Generated with Claude Code
