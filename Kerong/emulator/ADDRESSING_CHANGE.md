# Device Addressing - Version Differences

## Summary

**V3 uses 1-based addressing (devices 1-10), while V1 and V2 use 0-based addressing (devices 0-9).**

## Addressing by Version

### V3 (CU48 Protocol) - 1-Based Addressing:
- Selecting "1 device" emulates device address **1** (0x01)
- Selecting "10 devices" emulates addresses **1 through 10** (0x01-0x0A)
- Device addresses: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
- **This matches standard CU48 protocol convention**

### V1 & V2 (Generic Modbus) - 0-Based Addressing:
- Selecting "1 device" emulates device address **0** (0x00)
- Selecting "10 devices" emulates addresses **0 through 9** (0x00-0x09)
- Device addresses: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9

## Why Different Addressing?

### V3 (1-based):
- **CU48 Protocol Standard**: Real CU48 devices use addresses starting at 1
- **Industry Convention**: Lock controllers typically don't use address 0
- **Protocol Compliance**: Matches actual hardware behavior for accurate testing

### V1 & V2 (0-based):
- **Generic Modbus Testing**: Address 0 is valid and commonly used in Modbus
- **Zero-based indexing**: Consistent with programming conventions
- **Flexibility**: Allows testing with device address 0

## What You Need to Know

### Using V3 (CU48 Protocol):
**Send requests to device address 1 (0x01) for the first device**

Example request for first device:
```
Address 1: 01 03 00 0F 00 01 [CRC]
           ^^
           Device address 1 (0x01)
```

### Multiple Devices by Version:

**V3 (CU48) - 1-based addressing:**
- 1 device: address 1
- 2 devices: addresses 1, 2
- 5 devices: addresses 1, 2, 3, 4, 5
- 10 devices: addresses 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

**V1 & V2 (Generic) - 0-based addressing:**
- 1 device: address 0
- 2 devices: addresses 0, 1
- 5 devices: addresses 0, 1, 2, 3, 4
- 10 devices: addresses 0, 1, 2, 3, 4, 5, 6, 7, 8, 9

## Default Register Values

Special register values per version:

**V3: Device 1 has:**
- Holding Register 0x0F = 0xE230 (57904)
- Holding Register 0xF5 = 0x0002
- Holding Register 0xF6 = 0x0004

**V1 & V2: Device 0 has:**
- Holding Register 0x0F = 0xE230 (57904)
- Holding Register 0xF5 = 0x0002
- Holding Register 0xF6 = 0x0004

## GUI Display by Version

**V3 displays:**
- "Emulating devices: 1" (for 1 device)
- "Emulating devices: 1, 2" (for 2 devices)
- "Emulating devices: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10" (for 10 devices)

**V1 & V2 display:**
- "Emulating devices: 0" (for 1 device)
- "Emulating devices: 0, 1" (for 2 devices)
- "Emulating devices: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9" (for 10 devices)

## Test Updates

All tests match their respective version's addressing:
- ✅ V3 tests: Use 1-based addressing (device 1 = 0x01)
- ✅ V1 tests: Use 0-based addressing (device 0 = 0x00)
- ✅ V2 tests: Use 0-based addressing (device 0 = 0x00)

## Files Per Version

### V3 (1-based addressing):
- `modbus_rtu_emulator_v3.py`
  - Device range: `range(1, num_devices + 1)` (addresses 1-10)
  - Default values: `device_id == 1`
  - GUI displays: devices 1-10
  - Device selector: 1-10

### V1 (0-based addressing):
- `modbus_rtu_emulator.py`
  - Device range: `range(0, num_devices)` (addresses 0-9)
  - Default values: `device_id == 0`
  - GUI displays: devices 0-9

### V2 (0-based addressing):
- `modbus_rtu_emulator_v2.py`
  - Device range: `range(0, num_devices)` (addresses 0-9)
  - Default values: `device_id == 0`
  - GUI displays: devices 0-9

### Tests:
- `test_emulator_v3.py` - Uses device address 0x01
- `test_emulator.py` - Uses device address 0x00
- `test_emulator_v2.py` - Uses device address 0x00

## Migration Guide

### If you're using a Modbus master:

1. **Update your master device configuration** to send requests to address 0 instead of 1
2. **Update any hardcoded device addresses** in your code from 1 to 0
3. **Retest your communication** to verify everything works

### Example Code Change (Python):

**Before:**
```python
# Read holding register from device 1
request = struct.pack('>BBHHH', 1, 3, 0x0F, 1, crc)
                                 ^
                                 Was 1
```

**After:**
```python
# Read holding register from device 0
request = struct.pack('>BBHHH', 0, 3, 0x0F, 1, crc)
                                 ^
                                 Now 0
```

## Verification

To verify the change is working:

```bash
# Run V1 tests
python test_emulator.py
# Should see: "ALL TESTS PASSED!"

# Run V2 tests
python test_emulator_v2.py
# Should see: "ALL V2 TESTS PASSED!"
```

## Common Questions

**Q: Can I still use device address 1?**
A: Yes! If you select "2 devices" or more, device address 1 will be emulated. It's just no longer the first device.

**Q: Why not make this configurable?**
A: To keep the interface simple. Starting from 0 is the most flexible option as it allows you to test with address 0.

**Q: Will my old logs/statistics still make sense?**
A: Device statistics will now show "Device 00" instead of "Device 01", but the functionality is identical.

**Q: Do I need to change my RS485 wiring?**
A: No! This is purely a software change. The physical connection remains the same.

## Troubleshooting

**Problem: Master not getting responses**
- **Solution**: Check that your master is sending to device address 0 (not 1)

**Problem: Only some devices responding**
- **Solution**: Verify you're sending to addresses 0-9 (not 1-10)

**Problem: Tests failing**
- **Solution**: Ensure you're running the updated test files

## Summary

✅ **V1 Updated**: Devices 0-9
✅ **V2 Updated**: Devices 0-9
✅ **Tests Updated**: All passing
✅ **Backward Compatible**: Select 10 devices to include address 1-9

The change is complete and both versions are fully tested and working with 0-based addressing!
