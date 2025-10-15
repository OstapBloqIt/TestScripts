# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Modbus RTU Slave Emulator** for Windows that emulates CU48 lock controller devices over RS485 serial communication. The project has three versions, with **V3 being the current production version**.

### Version Evolution
- **V1** (`modbus_rtu_emulator.py`): Basic multi-device Modbus RTU emulation
- **V2** (`modbus_rtu_emulator_v2.py`): Added detailed error tracking with last 5 errors analysis
- **V3** (`modbus_rtu_emulator_v3.py`): **CURRENT VERSION** - CU48-specific protocol with 48 locks per device, command logging, and GUI lock control

## Running & Testing

### Run the Emulator
```bash
# Run V3 (recommended - CU48 protocol)
python modbus_rtu_emulator_v3.py

# Run V2 (enhanced error tracking)
python modbus_rtu_emulator_v2.py

# Run V1 (basic)
python modbus_rtu_emulator.py
```

### Run Tests
```bash
# Test V3 (CU48 protocol compliance)
python test_emulator_v3.py

# Test V2 (error tracking features)
python test_emulator_v2.py

# Test V1 (basic functionality)
python test_emulator.py

# Test command logging feature
python test_command_logging.py
```

All tests should output "ALL TESTS PASSED!" or similar success message.

### Dependencies
```bash
pip install -r requirements.txt
# Only requires: pyserial==3.5
# tkinter is included with Python on Windows
```

## Architecture

### Three-Layer Architecture

1. **Device Layer** (`CU48Device` / `ModbusSlaveDevice`)
   - Each device emulates a single Modbus slave
   - V3: Stores 48 locks as boolean array (True = closed/locked, False = unlocked)
   - Processes Modbus function codes (0x01, 0x03, 0x05, 0x06, 0x0F, 0x10)
   - Returns proper exception responses for invalid requests

2. **Emulator Layer** (`ModbusRTUEmulator`)
   - Manages multiple devices (up to 10, addresses 1-10 / 0x01-0x0A)
   - Handles serial port communication (RS485 half-duplex)
   - Frame detection using 3.5 character time (10ms at 9600 baud)
   - Routes requests to appropriate device based on address
   - Collects statistics and logs commands

3. **GUI Layer** (`EmulatorGUI`)
   - tkinter-based Windows interface
   - V3 features:
     - Lock Control tab: 48-lock visual grid (green=closed, red=unlocked)
     - Command Log tab: Shows ALL bus traffic (valid and invalid frames)
     - Statistics tab: Real-time Modbus statistics
     - Last 5 Errors tab: Detailed error analysis with frame highlighting
     - System Log tab: Application events

### Key Architectural Concepts

#### 1-Based Device Addressing
**CRITICAL**: V3 uses 1-based addressing (devices 1-10, addresses 0x01-0x0A).
- Selecting "1 device" emulates device address **1** (0x01)
- Selecting "10 devices" emulates addresses **1 through 10** (0x01-0x0A)
- Device address 0x00 is not used (reserved for broadcast in Modbus)

#### CU48 Protocol (V3 Only)
- **48 locks per device** (coil addresses 0x00-0x2F)
- **Default state**: All locks initialize as CLOSED (coil value = 1)
- **Lock semantics**: 1 = closed/locked, 0 = unlocked/open
- **Status encoding**: 48 bits packed into 6 bytes, LSB first
- **Default baud rate**: 115200 (CU48 standard)

#### Command Logging (V3 Only)
The command log captures **ALL RS485 bus traffic**:
- Every received frame (even invalid ones with bad CRC)
- CRC validation status (✓ Valid or ✗ Invalid)
- Response status (sent, not sent, or no response reason)
- Detailed parameter decoding for valid commands

This is critical for debugging communication issues, especially when you see high invalid request counts.

#### Frame Processing Flow
```
Receive bytes → Buffer until 10ms silence → Parse frame header →
Validate CRC → Check device address → Route to device →
Generate response → Send with 2ms delay → Log to command log
```

#### CRC-16 Calculation
- Polynomial: 0xA001
- Initial value: 0xFFFF
- Byte order: Low byte first (little-endian)
- Functions: `calculate_crc16()`, `crc16_bytes()`, `verify_crc()`

## Common Development Tasks

### Adding a New Modbus Function Code
1. Add handler method in device class (e.g., `read_input_registers()`)
2. Add case in `process_request()` method
3. Handle exception responses (return `_exception_response()`)
4. Update `_log_command()` in emulator to decode parameters
5. Add test case in `test_emulator_v3.py`

### Modifying Lock Behavior (V3)
- Lock states stored in `CU48Device.coils[]` (48-element boolean array)
- Index 0 = Lock #1, Index 47 = Lock #48
- GUI callbacks update via `lock_state_callback`
- Lock operations tracked in `Statistics.locks_unlocked` / `locks_locked`

### Adding GUI Features
- GUI uses tkinter `ttk.Notebook` with tabs
- Lock buttons stored in `EmulatorGUI.lock_buttons` dict
- Update methods run on 1-second timer via `root.after()`
- Use callbacks for thread-safe updates from emulator to GUI

## Important Implementation Details

### Exception Response Format
Modbus exception responses have high bit set on function code:
```python
# Normal response: [device_addr, function_code, data...]
# Exception response: [device_addr, function_code | 0x80, exception_code]
```

Exception codes: 0x01 (illegal function), 0x02 (illegal address), 0x03 (illegal value), 0x04 (device failure)

### Thread Safety
- Serial port runs in daemon thread (`_receive_loop()`)
- GUI updates use callbacks with `root.after()` for thread safety
- Statistics access is not mutex-protected (acceptable for read-only display)

### Half-Duplex Timing
- 2ms delay before sending response (`time.sleep(0.002)`)
- 10ms frame timeout for detecting frame boundaries
- Critical for RS485 bus collision avoidance

### Testing Philosophy
- Each version has dedicated test file
- Tests use direct `_process_frame()` calls (no serial port required)
- All tests verify CRC calculation, request/response format, and protocol compliance
- Boundary conditions explicitly tested (e.g., lock 48 valid, lock 49 invalid)

## Troubleshooting Common Issues

### High Invalid Request Count
Check Command Log tab to see:
- Are frames targeting wrong device address? (e.g., device 5 when only device 1 emulated)
- Are CRC errors present? (suggests baud rate mismatch or electrical issues)
- Are frames truncated? (framing errors suggest timing or noise issues)

### No Responses Sent
- Verify device address matches emulated devices (1-10 / 0x01-0x0A)
- Check baud rate matches master (default: 115200 for CU48)
- Ensure RS485 wiring correct (A/B not swapped)
- Look for CRC errors in Command Log

### Locks Not Updating in GUI
- Ensure correct device selected in spinner
- Check if emulator is running (green status)
- Verify `_update_lock_display()` called after state changes
- Check `lock_state_callback` is set

## File Reference

### Core Files
- `modbus_rtu_emulator_v3.py` - Main V3 application (CU48 protocol)
- `test_emulator_v3.py` - V3 test suite (CU48 compliance)
- `test_command_logging.py` - Command logging feature tests

### Documentation
- `CU48_V3_README.md` - V3 user guide with protocol examples
- `ADDRESSING_CHANGE.md` - Critical: explains 0-based addressing
- `COMMAND_LOGGING.md` - Command logging feature documentation

### Legacy Files
- `modbus_rtu_emulator_v2.py` / `test_emulator_v2.py` - V2 with error tracking
- `modbus_rtu_emulator.py` / `test_emulator.py` - V1 basic version

## CU48 Protocol Quick Reference

### Modbus Function Codes
- **0x01**: Read Coils (lock status) - Returns 6 bytes for 48 locks
- **0x03**: Read Holding Registers - Configuration/settings
- **0x05**: Write Single Coil - Unlock (0x0000) or Lock (0xFF00)
- **0x06**: Write Single Register - Configuration write
- **0x0F**: Write Multiple Coils - Unlock/lock multiple locks
- **0x10**: Write Multiple Registers - Multi-register write

### Lock Address Mapping
```
Lock #1  → Coil 0x00 → Byte 0, Bit 0
Lock #8  → Coil 0x07 → Byte 0, Bit 7
Lock #9  → Coil 0x08 → Byte 1, Bit 0
Lock #48 → Coil 0x2F → Byte 5, Bit 7
```

### Default Register Values (Device 1 only)
- Register 0x0F = 0xE230 (57904)
- Register 0xF5 = 0x0002
- Register 0xF6 = 0x0004
- Register 0x03 = 550 (unlock duration in ms)
