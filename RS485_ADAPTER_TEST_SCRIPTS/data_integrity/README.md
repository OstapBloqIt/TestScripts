# RS485 Data Integrity Test

Data integrity testing suite for SP3485EN-based RS485 to TTL adapter with comprehensive BER (Bit Error Rate) analysis.

## Hardware Setup

```
PC (USB) <---> USB-RS485 Adapter <---> [A+/B- lines] <---> SP3485EN Adapter <---> [RX/TX TTL] <---> ESP32-S3-Zero
```

### Connections

1. **ESP32-S3-Zero to SP3485EN Adapter (TTL side)**
   - ESP32 TX (GPIO43) → Adapter RX
   - ESP32 RX (GPIO44) → Adapter TX
   - GND → GND

2. **SP3485EN Adapter to USB-RS485 (Differential lines)**
   - Adapter A+ → USB-RS485 A+
   - Adapter B- → USB-RS485 B-

3. **USB-RS485 to PC**
   - Connect via USB cable

## Test Patterns

The test suite includes 8 robust data patterns:

1. **Sequential** - Incrementing bytes (0x00, 0x01, ..., 0xFF)
2. **Alternating** - Alternating pattern (0xAA, 0x55)
3. **All Zeros** - Continuous 0x00 bytes
4. **All Ones** - Continuous 0xFF bytes
5. **Random** - Pseudo-random bytes with fixed seed
6. **Walking Ones** - Bit-walking pattern (0x01, 0x02, 0x04, 0x08...)
7. **Walking Zeros** - Inverted bit-walking pattern
8. **PRBS-7** - Pseudo-Random Binary Sequence

## Software Setup

### ESP32-S3 Program

1. Open `esp32_test.ino` in Arduino IDE
2. Install ESP32 board support if needed
3. Select board: "ESP32S3 Dev Module" or "ESP32-S3-Zero"
4. Verify GPIO pins match your board (default: RX=44, TX=43)
5. Upload to ESP32-S3
6. Open Serial Monitor (115200 baud) to view debug output

### PC Program

1. Install Python 3 and required packages:
   ```bash
   pip install pyserial
   ```

2. Run the test:
   ```bash
   python pc_test.py
   ```

3. Follow the prompts:
   - Enter your COM port (e.g., COM3)
   - Select test pattern (1-8)
   - For Random/PRBS patterns, optionally enter a seed

## Test Configuration

- **Baud Rate:** 9600 bps
- **Data Length:** 1000 bytes
- **Format:** 8N1 (8 data bits, no parity, 1 stop bit)

## Test Procedure

1. Power up ESP32-S3 and verify it's running (check Serial Monitor)
2. Connect all hardware as described above
3. Run `pc_test.py` on your PC
4. Select desired test pattern
5. Test automatically:
   - Generates pattern data
   - Sends data to ESP32 via RS485
   - ESP32 echoes data back
   - PC receives and compares with sent data
   - BER is calculated and displayed

## Results Analysis

The test reports:
- **Total bytes/bits** transmitted
- **Byte errors** - Number of corrupted bytes
- **Bit errors** - Number of individual bit flips
- **Byte Error Rate (%)** - Percentage of corrupted bytes
- **Bit Error Rate (%)** - Percentage of corrupted bits
- **Error positions** - First 10 error locations with details

### Success Criteria

- **BER = 0%** → Perfect transmission, adapter working correctly
- **BER > 0%** → Data corruption detected, check:
  - Cable connections
  - Termination resistors (120Ω on long cables)
  - Grounding
  - Electrical noise
  - Adapter hardware

## Troubleshooting

### No data received
- Check all connections
- Verify COM port is correct
- Ensure ESP32 is running (check debug output)
- Test with loopback (short A+ to B+ on PC side)

### High BER
- Check cable quality and length
- Add 120Ω termination resistors on A+/B- lines
- Reduce cable length
- Check power supply stability
- Test with different patterns (some patterns more sensitive to noise)

### Timeout errors
- Increase timeout in `pc_test.py` if using slower baud rates
- Check ESP32 is powered and running
- Verify Serial1 pins in ESP32 code match your hardware

## GPIO Pin Configuration

Default ESP32-S3-Zero UART pins:
```cpp
#define RXD2 44  // GPIO44
#define TXD2 43  // GPIO43
```

**Important:** Verify these match your specific ESP32-S3 board variant!

Common alternatives:
- Some boards use GPIO16 (RX) and GPIO17 (TX)
- Check your board's pinout diagram

## Expected Performance

At 9600 baud:
- Transmission time: ~1.04 seconds (1000 bytes)
- Round-trip time: ~2-3 seconds
- Theoretical BER: 0% (with proper hardware setup)
