# Command Logging Feature - V3

## Overview

Version 3 now includes comprehensive **command logging** that captures and decodes every Modbus RTU command received by the emulator. This feature provides detailed insight into all communication between the master and the CU48 slave devices.

## Features

### What Gets Logged

Every valid Modbus command is logged with:
- **Timestamp**: When the command was received
- **Device Address**: Which device (0x00-0x09)
- **Function Code & Name**: e.g., 0x01 = Read Coils
- **Raw Request**: Complete hex dump of received frame
- **Raw Response**: Complete hex dump of response sent
- **Decoded Parameters**: Human-readable parameter breakdown
- **Result**: What happened (e.g., "LOCK #5 UNLOCKED")

### Command Log Tab

A new **"Command Log"** tab in the GUI displays all received commands in real-time with:
- Blue text for easy visibility
- Scrollable history
- Formatted display with separators
- Auto-scroll to latest command

### Supported Commands

All CU48 Modbus functions are decoded:

#### Read Operations
- **0x01 - Read Coils**: Shows start address, count, and returned lock status bytes
- **0x02 - Read Discrete Inputs**: Shows start address, count, and data
- **0x03 - Read Holding Registers**: Shows start address, count, and register count
- **0x04 - Read Input Registers**: Shows start address, count, and register count

#### Write Operations
- **0x05 - Write Single Coil**: Shows lock number, action (Unlock/Close), and result
- **0x06 - Write Single Register**: Shows register address, value (hex and decimal)
- **0x0F - Write Multiple Coils**: Shows start lock, count, data bytes, and operations
- **0x10 - Write Multiple Registers**: Shows start address, count, bytes written

### GUI Controls

New buttons in the action bar:
- **"Clear Command Log"**: Clears the command log display
- **"Save Command Log"**: Saves log to timestamped file

The existing "Communication Log" tab has been renamed to "System Log" for clarity.

## Example Command Logs

### Read 48 Lock Status
```
[2025-10-15 12:33:27.746] Device 0x00 - Read Coils (0x01)
  Request:  00 01 00 00 00 30 3D CF
  Response: 00 01 06 FF FF FF FF FF FF AC B3
  Parameters: Start: 0x0000 (0), Count: 48
  Result: Returned 6 bytes: FF FF FF FF FF FF
----------------------------------------------------------------------
```

### Unlock Single Lock
```
[2025-10-15 12:33:28.123] Device 0x00 - Write Single Coil (0x05)
  Request:  00 05 00 00 00 00 CC 1B
  Response: 00 05 00 00 00 00 CC 1B
  Parameters: Lock #1 (0x0000), Value: OFF (Unlock)
  Result: LOCK #1 UNLOCKED
----------------------------------------------------------------------
```

### Close/Lock Single Lock
```
[2025-10-15 12:33:28.456] Device 0x00 - Write Single Coil (0x05)
  Request:  00 05 00 00 FF 00 CC 2A
  Response: 00 05 00 00 FF 00 CC 2A
  Parameters: Lock #1 (0x0000), Value: ON (Close/Lock)
  Result: LOCK #1 CLOSED
----------------------------------------------------------------------
```

### Unlock Multiple Locks
```
[2025-10-15 12:33:29.789] Device 0x00 - Write Multiple Coils (0x0F)
  Request:  00 0F 00 00 00 08 01 00 3F 59
  Response: 00 0F 00 00 00 08 55 DC
  Parameters: Start: 0x0000 (Lock #1), Count: 8, Data: 00
  Result: Lock #1 UNLOCKED; Lock #2 UNLOCKED; ... Lock #8 UNLOCKED
----------------------------------------------------------------------
```

### Read Holding Registers
```
[2025-10-15 12:33:30.012] Device 0x00 - Read Holding Registers (0x03)
  Request:  00 03 00 0F 00 01 B4 09
  Response: 00 03 02 E2 30 B8 FA
  Parameters: Start: 0x000F (15), Count: 1
  Result: Returned 1 registers (2 bytes)
----------------------------------------------------------------------
```

## Saving Command Logs

### Auto-Generated Filename
Command logs are saved with timestamp:
```
modbus_cu48_commands_20251015_123456.log
```

### File Format
Saved files include:
- Header with generation timestamp
- All logged commands with full details
- Raw hex dumps for analysis
- Decoded parameters and results

Example saved file structure:
```
======================================================================
MODBUS RTU CU48 EMULATOR - COMMAND LOG
======================================================================
Generated: 2025-10-15 12:34:56
======================================================================

[2025-10-15 12:33:27.746] Device 0x00 - Read Coils (0x01)
  Request:  00 01 00 00 00 30 3D CF
  Response: 00 01 06 FF FF FF FF FF FF AC B3
  Parameters: Start: 0x0000 (0), Count: 48
  Result: Returned 6 bytes: FF FF FF FF FF FF
----------------------------------------------------------------------

[2025-10-15 12:33:28.123] Device 0x00 - Write Single Coil (0x05)
  Request:  00 05 00 00 00 00 CC 1B
  Response: 00 05 00 00 00 00 CC 1B
  Parameters: Lock #1 (0x0000), Value: OFF (Unlock)
  Result: LOCK #1 UNLOCKED
----------------------------------------------------------------------

...
```

## Integration with System Log

Important lock operations are also logged to the "System Log" for quick visibility:
```
[2025-10-15 12:33:28.123] CMD: Device 0 - LOCK #1 UNLOCKED
[2025-10-15 12:33:28.456] CMD: Device 0 - LOCK #1 CLOSED
```

## Use Cases

### Debugging Communication Issues
- See exactly what commands are being received
- Verify request/response formats
- Check CRC calculations
- Identify malformed requests

### Protocol Analysis
- Understand master device behavior
- Analyze command patterns
- Verify protocol compliance
- Document communication sequences

### Testing & Validation
- Confirm all commands work as expected
- Verify lock state changes
- Test multiple device addressing
- Validate exception handling

### Audit Trail
- Keep record of all lock operations
- Track who unlocked which locks (by device)
- Timestamp all operations
- Export logs for review

## Technical Implementation

### CommandLog Class
Dataclass that stores:
```python
@dataclass
class CommandLog:
    timestamp: str
    device_addr: int
    function_code: int
    function_name: str
    raw_request: bytes
    raw_response: bytes
    parameters: str
    result: str
```

### Callback Architecture
```python
# Set callback in emulator
emulator.set_command_log_callback(callback_function)

# Callback receives CommandLog object
def callback_function(command_log: CommandLog):
    # Process the log entry
    print(command_log.format_log())
```

### Decoding Logic
Each function code has specific decoding:
- Extracts addresses, counts, values from request
- Formats parameters in human-readable form
- Describes the result/operation
- Handles exceptions gracefully

## Performance

- **Minimal Overhead**: Logging occurs asynchronously
- **No Impact on Timing**: Responses sent before logging completes
- **Memory Efficient**: Only GUI display stores history
- **Thread-Safe**: Callback mechanism ensures no conflicts

## Benefits Over System Log

| Feature | Command Log | System Log |
|---------|-------------|-----------|
| **Detail Level** | Full hex dumps + decode | Summary only |
| **Request/Response** | Both shown | Not shown |
| **Parameters** | Fully decoded | Limited |
| **Lock Operations** | Every detail | Major events only |
| **Saveable** | Yes, dedicated file | Yes, mixed content |
| **Real-time** | Yes | Yes |
| **Color Coded** | Blue text | Black text |

## Example Workflow

1. **Start Emulator** with command logging enabled
2. **Send Commands** from Modbus master device
3. **View Commands** in real-time on "Command Log" tab
4. **Analyze Patterns** - see what master is requesting
5. **Debug Issues** - check for malformed requests
6. **Save Log** - export for documentation or analysis
7. **Clear Log** - start fresh for new test

## Future Enhancements

Potential improvements:
- Filter by device address
- Filter by function code
- Search/highlight capability
- Export to CSV format
- Statistics per command type
- Timing analysis (response times)

## Testing

Run the command logging test:
```bash
python test_command_logging.py
```

Expected output:
```
✅ Command logging test PASSED!

Logged command summaries:
  1. Read Coils: Returned 6 bytes: FF FF FF FF FF FF
  2. Write Single Coil: LOCK #1 UNLOCKED
  3. Write Single Coil: LOCK #1 CLOSED
```

## Summary

The command logging feature provides complete visibility into all Modbus RTU communication with the CU48 emulator. Every command is captured, decoded, and displayed in an easy-to-read format, making debugging, testing, and protocol analysis much easier!
