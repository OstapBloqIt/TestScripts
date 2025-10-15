# Modbus RTU Slave Emulator - Version 2

Enhanced version with detailed error tracking and analysis.

## What's New in V2

### Enhanced Error Tracking

Version 2 adds comprehensive error analysis with the following features:

1. **Last 5 Errors Display**
   - New dedicated "Last 5 Errors" tab in the GUI
   - Shows the most recent errors in detail
   - Automatically updated in real-time

2. **Detailed Error Analysis**
   - Frame-by-frame byte display
   - Error position highlighting with `[XX]` and `^^` markers
   - Shows what was received vs what was expected
   - Complete frame structure decoding

3. **Error Types Tracked**
   - **CRC Errors**: Shows received CRC vs expected CRC
   - **Framing Errors**: Identifies incomplete or malformed frames
   - **Unsupported Functions**: Highlights invalid function codes
   - **Timeout Errors**: Tracks communication timeouts

## Error Display Example

When a CRC error occurs, V2 shows:

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
======================================================================
```

### Key Features

- **Error Position Highlighting**: The `[XX]` brackets and `^^` markers show exactly where the error occurred
- **Expected vs Actual**: For CRC errors, shows both what was received and what should have been sent
- **Frame Decoding**: Automatically decodes device address, function code, and other fields
- **Timestamp**: Each error includes precise timestamp (millisecond accuracy)

## GUI Changes

### New "Last 5 Errors" Tab

The V2 GUI includes a new tab specifically for error analysis:

- **Real-time Stats** - General statistics (same as V1)
- **Last 5 Errors** - NEW! Detailed error analysis
- **Communication Log** - Event log (same as V1)

### New Button

- **Clear Errors** - Clears the error history display

## Installation & Usage

Same as V1, but run the V2 file:

```bash
# Install dependencies (same as V1)
pip install -r requirements.txt

# Run V2 tests
python test_emulator_v2.py

# Launch V2 GUI
python modbus_rtu_emulator_v2.py
```

## Use Cases for V2

### 1. Debugging Communication Issues

When you have intermittent errors, V2 helps you:
- See exactly which bytes are wrong
- Identify patterns in errors (always same device? same function?)
- Quickly spot CRC calculation issues

### 2. Protocol Validation

Verify your master device's implementation:
- Check if CRCs are calculated correctly
- Ensure frames are properly formatted
- Validate function codes are standard

### 3. Hardware Troubleshooting

Electrical noise or wiring issues show up as:
- Random CRC errors (single bit flips)
- Framing errors (timing issues)
- Consistent byte position errors (termination problems)

### 4. Development & Testing

During development:
- Instantly see malformed requests
- Compare expected vs actual values
- Track error frequency and patterns

## Error Analysis Details

### CRC Errors

```
Received CRC:   AABB
Expected CRC:   B409
```

Shows:
- What CRC was in the frame
- What the CRC should have been
- Highlights the CRC bytes in the frame

### Framing Errors

```
Description: Frame too short: 2 bytes (minimum 4 bytes required)
```

Shows:
- Why the frame is invalid
- How many bytes were received
- What the minimum requirement is

### Unsupported Function Errors

```
Function Code:  0x50 (Unknown/Invalid)
Error at byte position 1
```

Shows:
- The invalid function code
- Position in the frame
- Highlights the function code byte

## Comparing V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| Multi-device emulation (1-10) | ✓ | ✓ |
| All Modbus functions | ✓ | ✓ |
| Error counting | ✓ | ✓ |
| Statistics | ✓ | ✓ |
| Communication log | ✓ | ✓ |
| **Detailed error analysis** | ✗ | ✓ |
| **Error position highlighting** | ✗ | ✓ |
| **Expected vs actual display** | ✗ | ✓ |
| **Last 5 errors tracking** | ✗ | ✓ |
| **Frame-by-frame decoding** | ✗ | ✓ |

## When to Use V1 vs V2

### Use V1 when:
- You just need basic emulation
- No debugging required
- Lighter resource usage preferred
- Simpler interface desired

### Use V2 when:
- Debugging communication issues
- Need detailed error analysis
- Troubleshooting electrical problems
- Validating master device implementation
- Development and testing

## Technical Implementation

### ErrorDetail Class

```python
@dataclass
class ErrorDetail:
    timestamp: str
    error_type: str
    frame: bytes
    description: str
    expected_value: Optional[bytes] = None
    error_position: Optional[int] = None
```

### Error Tracking

V2 uses a deque with maxlen=5 to automatically maintain the last 5 errors:

```python
recent_errors: deque = field(default_factory=lambda: deque(maxlen=5))
```

When the 6th error arrives, the oldest is automatically discarded.

### Frame Analysis

V2 automatically decodes:
- Device address (byte 0)
- Function code (byte 1) with name lookup
- CRC bytes (last 2 bytes)
- Data portion (bytes 2 to -2)

## Saving Statistics in V2

When you click "Save Statistics" in V2, the saved file includes:

1. Standard statistics summary
2. Last 5 errors with full details

Example filename: `modbus_stats_v2_20251014_174500.txt`

## Performance

V2 has minimal performance impact:
- Error tracking: <1ms overhead
- GUI update: Every 1 second (same as V1)
- Memory: ~5KB per error × 5 = ~25KB total for error queue

## Upgrading from V1 to V2

V2 is a separate file, so you can run both:
- Keep V1 for production use
- Use V2 for debugging and development

Or simply switch to V2 exclusively - it includes all V1 features plus error analysis.

## Example Workflow

1. **Start emulator** with V2
2. **Run your master device**
3. **Monitor "Last 5 Errors" tab** if issues occur
4. **Identify error patterns**:
   - Always same device? → Check device address configuration
   - Always CRC errors? → Check electrical connections
   - Always same function? → Check master's function code implementation
5. **Save statistics** including error details for analysis
6. **Fix issues** based on detailed error information

## Troubleshooting with V2

### All Errors are CRC Errors
**Problem**: Electrical noise, bad grounding, or termination issues
**Solution**: Check RS485 wiring, add/check termination resistors, reduce baud rate

### Random Byte Corruptions
**Problem**: Single-bit errors in random positions
**Solution**: Electromagnetic interference, keep cables away from power lines

### Consistent Framing Errors
**Problem**: Timing issues, baud rate mismatch
**Solution**: Verify baud rate matches, check for clock drift

### Same Byte Position Always Wrong
**Problem**: Software bug in master device
**Solution**: Check master's frame construction code

## Support

For V2-specific issues, include:
1. Screenshot of "Last 5 Errors" tab
2. Saved statistics file
3. Description of what you expected vs what happened

## Future Enhancements

Possible V3 features:
- [ ] Configurable error queue size (more than 5)
- [ ] Error filtering (show only CRC errors, etc.)
- [ ] Error export to CSV
- [ ] Statistical error analysis (most common error type, etc.)
- [ ] Visual error rate graphing

## License

Same as V1 - provided for testing and development purposes.
