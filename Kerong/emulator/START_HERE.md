# Modbus RTU Slave Emulator - START HERE

## Welcome!

This directory contains **two versions** of a professional Modbus RTU slave emulator for Windows.

## Quick Decision Guide

**Just want to test Modbus communication?**
→ Use **Version 1** (simpler, straightforward)

**Need to debug errors or see what's wrong with frames?**
→ Use **Version 2** (detailed error analysis)

**Not sure?**
→ Start with **Version 2** (includes everything from V1)

## Installation (Both Versions)

```bash
pip install -r requirements.txt
```

## Quick Start

### Version 1 (Basic)
```bash
# Run tests
python test_emulator.py

# Launch GUI
python modbus_rtu_emulator.py
```

### Version 2 (Enhanced)
```bash
# Run tests
python test_emulator_v2.py

# Launch GUI
python modbus_rtu_emulator_v2.py
```

## What Each Version Does

### Version 1 Features
✓ Emulate 1-10 Modbus slave devices
✓ Full Modbus RTU protocol (8 functions)
✓ RS485 half-duplex communication
✓ Statistics (requests, errors, data transfer)
✓ Per-device and per-function tracking
✓ Windows GUI with real-time display
✓ Export statistics to file

### Version 2 Features (All V1 features PLUS)
✓ **Last 5 errors displayed in detail**
✓ **Frame-by-frame byte analysis**
✓ **Error position highlighting**
✓ **Expected vs actual value comparison**
✓ **Complete frame structure decoding**
✓ **Dedicated error analysis tab**
✓ **Enhanced debugging capabilities**

## Files in This Directory

### Applications
- `modbus_rtu_emulator.py` - Version 1 application
- `modbus_rtu_emulator_v2.py` - Version 2 application (enhanced)

### Tests
- `test_emulator.py` - V1 test suite
- `test_emulator_v2.py` - V2 test suite (includes error tracking tests)

### Documentation
- `START_HERE.md` - This file
- `README.md` - Complete V1 documentation
- `README_V2.md` - V2 features and changes
- `QUICKSTART.md` - Step-by-step getting started
- `PROJECT_SUMMARY.md` - Technical overview
- `V1_VS_V2_COMPARISON.md` - Detailed version comparison

### Configuration
- `requirements.txt` - Python dependencies (same for both)

## Example: Error Display Difference

### V1 Shows:
```
ERRORS:
  CRC Errors:         3
  Framing Errors:     2
```

### V2 Shows:
```
[2025-10-14 17:45:00.000] CRC ERROR
Description: CRC mismatch in register read request

Received Frame (8 bytes):
   01   03   00   0F   00   01  [AA]  BB
                                 ^^
  Error at byte position 6

Frame Analysis:
  Device Address: 0x01 (1)
  Function Code:  0x03 (Read Holding Registers)
  Received CRC:   AABB (bytes 6:8)
  Expected CRC:   B409
  CRC Difference: MISMATCH
```

See the difference? **V2 shows you exactly what's wrong!**

## Typical Workflow

1. **Install**: `pip install -r requirements.txt`
2. **Test**: Run test script to verify installation
3. **Launch**: Start the GUI application
4. **Configure**: Select COM port, baud rate, device count
5. **Start**: Click "Start Emulator"
6. **Monitor**: Watch statistics in real-time
7. **Debug** (V2 only): Check "Last 5 Errors" tab if issues occur
8. **Save**: Export statistics when done

## Hardware Setup

1. Connect RS485 USB adapter to PC
2. Connect adapter to RS485 bus (A/B terminals)
3. Ensure proper termination (120Ω resistors)
4. Verify master device is on same bus
5. Match baud rates between master and emulator

## Common Use Cases

### 1. Testing a New Master Device
**Use**: V1 or V2
**Why**: Verify master can communicate with slaves

### 2. Debugging Communication Errors
**Use**: V2
**Why**: See exactly what frames are wrong and why

### 3. Load Testing
**Use**: V1
**Why**: Simpler overhead for stress testing

### 4. Protocol Learning
**Use**: V2
**Why**: See frame structure and error details

### 5. Production Validation
**Use**: V1
**Why**: Proven, stable baseline

## Recommended Reading Order

**If you're new to this project:**
1. START_HERE.md (this file) ← You are here
2. QUICKSTART.md - Get running in 5 minutes
3. README.md or README_V2.md - Full documentation
4. V1_VS_V2_COMPARISON.md - Detailed comparison

**If you're a developer:**
1. PROJECT_SUMMARY.md - Architecture overview
2. test_emulator.py / test_emulator_v2.py - Code examples
3. README_V2.md - V2 enhancements

**If you have errors:**
1. README_V2.md - Error tracking features
2. V1_VS_V2_COMPARISON.md - See V2 advantages
3. Use V2 and check "Last 5 Errors" tab!

## Key Differences at a Glance

| Aspect | V1 | V2 |
|--------|----|----|
| **Purpose** | Emulation | Emulation + Debugging |
| **GUI Tabs** | 2 tabs | 3 tabs (adds "Last 5 Errors") |
| **Error Info** | Counts only | Detailed analysis |
| **File Size** | 25KB | 31KB (+6KB) |
| **Best For** | Production | Development/Debug |
| **Learning Curve** | Easy | Easy (same interface) |

## Support & Troubleshooting

### Installation Issues
- Ensure Python 3.7+ is installed
- Run `pip install -r requirements.txt`
- Check that pyserial installs correctly

### Serial Port Issues
- Verify COM port exists (check Device Manager)
- Close other applications using the port
- Check RS485 adapter is connected

### Communication Issues
- Verify baud rate matches master
- Check RS485 wiring (A/B connections)
- Ensure termination resistors present

### Error Analysis (V2)
- Check "Last 5 Errors" tab
- Look for patterns (same device? same function?)
- Save statistics for detailed review

## Next Steps

Choose your path:

**Path 1: Quick Test** (5 minutes)
1. `pip install -r requirements.txt`
2. `python test_emulator.py`
3. `python modbus_rtu_emulator.py`
4. Select COM port and click Start

**Path 2: With Understanding** (15 minutes)
1. Read QUICKSTART.md
2. Install and run tests
3. Read README.md or README_V2.md
4. Launch appropriate version

**Path 3: Deep Dive** (30 minutes)
1. Read PROJECT_SUMMARY.md
2. Review code in emulator files
3. Run both test suites
4. Compare V1 and V2 in action

## Additional Resources

- **Modbus Protocol**: [modbus.org](https://modbus.org)
- **RS485 Basics**: Search for "RS485 wiring guide"
- **Python Serial**: [pyserial.readthedocs.io](https://pyserial.readthedocs.io)

## License

Provided for testing and development purposes.

## Quick Command Reference

```bash
# Install
pip install -r requirements.txt

# Test V1
python test_emulator.py

# Test V2
python test_emulator_v2.py

# Run V1
python modbus_rtu_emulator.py

# Run V2
python modbus_rtu_emulator_v2.py
```

## Get Started Now!

1. Run: `pip install -r requirements.txt`
2. Run: `python test_emulator_v2.py`
3. Run: `python modbus_rtu_emulator_v2.py`
4. Configure and click "Start Emulator"

**That's it! You're now emulating Modbus slave devices!**

---

**Questions?** Check the README files for detailed information.

**Have errors?** Use V2 and check the "Last 5 Errors" tab.

**Want to contribute?** Review the code and test suites.

**Happy emulating!** 🎉
