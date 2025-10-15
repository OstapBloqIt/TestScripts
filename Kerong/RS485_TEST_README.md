# RS485 Communication Test Suite

This test suite validates RS485 communication between your iMX8M Mini (Linux) and Windows PC at multiple baud rates.

## Overview

The test suite consists of two Python scripts:
- **rs485_test_linux.py** - Runs on iMX8M Mini (Verdin SoM)
- **rs485_test_windows.py** - Runs on Windows PC

Both scripts support:
- Testing at multiple baud rates: 9600, 19200, 38400, 57600, 115200
- Echo server mode (receives and echoes back data)
- Sender mode (sends test packets and measures response)
- Round-trip time (RTT) measurements
- Comprehensive success rate statistics

---

## Hardware Setup

### iMX8M Mini Side
According to your system report, UART1 (`/dev/ttymxc0`) is connected to an RS485 transceiver.

```
Native UART Ports:
- /dev/ttymxc0 - Connected to RS485 transceiver
- /dev/ttymxc1 - Available
- /dev/ttymxc2 - Available
```

### Windows PC Side
- RS485-to-USB adapter (e.g., FTDI, Prolific, CH340)
- Appears as COM port (e.g., COM3, COM4)

### RS485 Wiring
Connect the RS485 transceivers:
```
Linux Side (iMX8M)          Windows Side (USB Adapter)
------------------          ---------------------------
RS485 A      <----------->  RS485 A
RS485 B      <----------->  RS485 B
GND          <----------->  GND (optional, recommended)
```

**Important**: Ensure proper RS485 termination resistors (120Ω) at both ends if cable length > 1 meter.

---

## Software Requirements

### Linux (iMX8M Mini)
```bash
# Python 3 (already installed on your system)
python3 --version

# Install pyserial
pip3 install pyserial

# Or use system package manager
apt-get install python3-serial
```

### Windows PC
```powershell
# Install Python 3.7 or later from python.org
python --version

# Install pyserial
pip install pyserial
```

---

## Installation

### On Linux (iMX8M Mini)
```bash
cd /tmp/TestScripts/Kerong

# Make script executable
chmod +x rs485_test_linux.py

# Verify Python and pyserial
python3 -c "import serial; print('pyserial OK')"
```

### On Windows PC
```powershell
# Download or copy rs485_test_windows.py to your PC
# Example: C:\RS485Test\

cd C:\RS485Test

# Verify Python and pyserial
python -c "import serial; print('pyserial OK')"
```

---

## Quick Start Guide

### Test Scenario 1: Windows Initiates, Linux Echoes

**Step 1: Start Linux Echo Server**
```bash
# On iMX8M Mini
cd /tmp/TestScripts/Kerong
python3 rs485_test_linux.py /dev/ttymxc0 --mode echo --baud 115200
```

**Step 2: Run Windows Sender Test**
```powershell
# On Windows PC (in another terminal)
python rs485_test_windows.py COM3 --mode sender
```

This will test all baud rates automatically!

---

### Test Scenario 2: Linux Initiates, Windows Echoes

**Step 1: Start Windows Echo Server**
```powershell
# On Windows PC
python rs485_test_windows.py COM3 --mode echo --baud 115200
```

**Step 2: Run Linux Sender Test**
```bash
# On iMX8M Mini (in another terminal)
python3 rs485_test_linux.py /dev/ttymxc0 --mode sender
```

---

## Detailed Usage

### Linux Script Options

```bash
# List help
python3 rs485_test_linux.py --help

# Run full test suite (all baud rates)
python3 rs485_test_linux.py /dev/ttymxc0 --mode sender

# Echo server at specific baud rate
python3 rs485_test_linux.py /dev/ttymxc0 --mode echo --baud 115200

# Echo server cycling through all baud rates (30 sec each)
python3 rs485_test_linux.py /dev/ttymxc0 --mode echo-cycle
```

### Windows Script Options

```powershell
# List available COM ports
python rs485_test_windows.py --list

# Run full test suite (all baud rates)
python rs485_test_windows.py COM3 --mode sender

# Echo server at specific baud rate
python rs485_test_windows.py COM3 --mode echo --baud 115200

# Echo server cycling through all baud rates
python rs485_test_windows.py COM3 --mode echo-cycle
```

---

## Understanding Test Results

### Successful Test Output

```
--- Testing Baud Rate: 115200 ---
Testing at 115200 baud...
  ✓ Packet 1/10: OK (RTT: 12.45 ms)
  ✓ Packet 2/10: OK (RTT: 11.89 ms)
  ✓ Packet 3/10: OK (RTT: 12.01 ms)
  ...

Results for 115200 baud:
  Success: 10/10 (100.0%)
  Failed:  0/10
  Avg RTT: 12.15 ms
```

### Test Summary

```
============================================================
TEST SUMMARY
============================================================
Baud Rate    Success    Failed     Rate       Avg RTT
------------------------------------------------------------
9600         10         0          100.0%     45.23 ms
19200        10         0          100.0%     24.15 ms
38400        10         0          100.0%     14.78 ms
57600        10         0          100.0%     12.89 ms
115200       10         0          100.0%     12.15 ms
============================================================

Overall Success Rate: 50/50 (100.0%)
Best Performing: 115200 baud (100.0% success, 12.15 ms RTT)
```

### What RTT Means

**RTT (Round-Trip Time)** measures the total time for:
1. Sending data from sender to receiver
2. Receiver processing and echoing back
3. Data returning to sender

Typical RTT values:
- **9600 baud**: 40-60 ms
- **19200 baud**: 20-30 ms
- **38400 baud**: 12-18 ms
- **57600 baud**: 10-15 ms
- **115200 baud**: 8-14 ms

---

## Troubleshooting

### Problem: "Port does not exist"

**Linux:**
```bash
# Check available UART ports
ls -l /dev/ttymxc*
ls -l /dev/ttyUSB*

# Your system has:
# /dev/ttymxc0, /dev/ttymxc1, /dev/ttymxc2
```

**Windows:**
```powershell
# List COM ports
python rs485_test_windows.py --list

# Or check Device Manager:
# Device Manager -> Ports (COM & LPT)
```

### Problem: "Permission denied" (Linux)

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Or run with sudo (not recommended)
sudo python3 rs485_test_linux.py /dev/ttymxc0 --mode sender
```

### Problem: "No response / Timeout"

**Check RS485 wiring:**
- Verify A-to-A and B-to-B connections
- RS485 polarity matters! Swapping A/B will cause no communication
- Check termination resistors (120Ω at both ends for long cables)

**Check baud rate matching:**
- Both sides must use the same baud rate
- Use `--baud` option to specify in echo mode

**Try different baud rates:**
```bash
# Test at lower baud rate first
python3 rs485_test_linux.py /dev/ttymxc0 --mode echo --baud 9600
```

### Problem: "Data mismatch"

This indicates data corruption. Possible causes:
- **Electrical noise** - Add/check termination resistors
- **Cable too long** - RS485 max distance ~1200m at low baud rates
- **Grounding issues** - Ensure common ground between devices
- **Baud rate too high** - Try lower baud rate (9600 or 19200)

### Problem: pyserial not found

```bash
# Linux
pip3 install pyserial
# or
apt-get install python3-serial

# Windows
pip install pyserial
```

---

## Advanced Testing

### Custom Test Parameters

You can modify the test parameters by editing the script:

```python
# At the top of the script
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]  # Add/remove rates
PACKETS_PER_TEST = 10  # Increase for longer tests
RESPONSE_TIMEOUT = 2.0  # Timeout in seconds
```

### Continuous Testing

For long-duration testing:

```bash
# Linux - Run test in loop
while true; do
    python3 rs485_test_linux.py /dev/ttymxc0 --mode sender
    sleep 5
done

# Windows - Run test in loop (PowerShell)
while ($true) {
    python rs485_test_windows.py COM3 --mode sender
    Start-Sleep -Seconds 5
}
```

### Logging Results

```bash
# Linux
python3 rs485_test_linux.py /dev/ttymxc0 --mode sender | tee rs485_test_$(date +%Y%m%d_%H%M%S).log

# Windows (PowerShell)
python rs485_test_windows.py COM3 --mode sender | Tee-Object -FilePath "rs485_test_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
```

---

## Test Scenarios

### Scenario 1: Bidirectional Full Test

Tests both directions with all baud rates.

**Terminal 1 (Linux):**
```bash
python3 rs485_test_linux.py /dev/ttymxc0 --mode sender
```

**Terminal 2 (Windows):**
```powershell
# Wait for Linux test to complete, then run:
python rs485_test_windows.py COM3 --mode sender
```

### Scenario 2: Stress Test

High-frequency testing for reliability:

Modify `PACKETS_PER_TEST = 100` in both scripts, then run full tests.

### Scenario 3: Different Baud Rates

Test specific baud rate only:

**Linux Echo:**
```bash
python3 rs485_test_linux.py /dev/ttymxc0 --mode echo --baud 57600
```

**Windows Sender (modify script to test single baud):**
```python
# Edit BAUD_RATES in rs485_test_windows.py
BAUD_RATES = [57600]  # Test only this rate
```

---

## Performance Expectations

### Theoretical vs Actual Throughput

| Baud Rate | Theoretical | Actual (with overhead) | RTT Expected |
|-----------|-------------|------------------------|--------------|
| 9600      | 960 B/s     | ~750 B/s              | 40-60 ms     |
| 19200     | 1920 B/s    | ~1500 B/s             | 20-30 ms     |
| 38400     | 3840 B/s    | ~3000 B/s             | 12-18 ms     |
| 57600     | 5760 B/s    | ~4500 B/s             | 10-15 ms     |
| 115200    | 11520 B/s   | ~9000 B/s             | 8-14 ms      |

### Success Rate Targets

- **Excellent**: 100% success rate
- **Good**: 95-99% success rate
- **Acceptable**: 90-95% success rate
- **Poor**: < 90% success rate (check wiring/interference)

---

## Next Steps

After successful testing:

1. **Document your results** - Save test logs for reference
2. **Choose optimal baud rate** - Based on success rate and latency requirements
3. **Implement your application** - Use the tested configuration
4. **Add error handling** - Based on observed failure patterns
5. **Consider protocol** - Add CRC, framing, or use Modbus RTU for RS485

---

## Example Application Code

Once testing is successful, here's a minimal example:

```python
import serial

# Use your tested configuration
ser = serial.Serial(
    port='/dev/ttymxc0',  # or 'COM3' on Windows
    baudrate=115200,       # Your best performing rate
    timeout=1.0
)

# Send data
ser.write(b"Hello RS485\n")

# Receive data
response = ser.read(100)
print(f"Received: {response}")

ser.close()
```

---

## Support

For issues or questions:
- Check troubleshooting section above
- Verify hardware connections
- Test with lower baud rates first
- Use echo mode to isolate sender vs receiver issues

---

## Test Configuration Summary

Based on your iMX8M Mini system:

**Linux Side:**
- Platform: iMX8M Mini Verdin SoM
- UART Port: `/dev/ttymxc0` (UART1 with RS485 transceiver)
- Driver: `imx-uart`

**Test Parameters:**
- Baud Rates: 9600, 19200, 38400, 57600, 115200
- Packets per test: 10
- Timeout: 2 seconds
- Test message format: `RS485_TEST_PACKET_<baudrate>_<seq>`

---

**Good luck with your RS485 testing!**
