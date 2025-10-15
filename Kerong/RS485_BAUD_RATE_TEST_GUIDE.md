# RS485 Baud Rate Sweep Test Guide

## Overview

This guide explains how to perform RS485 baud rate sweep testing between a PC (Windows) and an embedded Linux device (Toradex Verdin iMX8M Mini).

**Purpose:** Test RS485 communication reliability at multiple baud rates (9600, 19200, 38400, 57600, 115200 bps)

---

## Hardware Setup

### PC Side (Windows)
- **Device:** Windows PC with RS485-to-USB adapter
- **Port:** COM3 (or check Device Manager)
- **Software:** `pc_baud_rate_sweep.py`

### Linux Side (iMX8M Mini)
- **Device:** Toradex Verdin iMX8M Mini SoM
- **Port:** `/dev/ttymxc0` (native UART)
- **Software:** `rs485_listener_linux.py`

### Physical Connections
```
PC RS485 Adapter          Linux iMX8M Mini UART
    A+ ←------------------→ A+
    B- ←------------------→ B-
    GND ←-----------------→ GND
```

---

## Software Setup

### 1. Install Dependencies

**On Windows:**
```bash
pip install pyserial
```

**On Linux (iMX8M Mini):**
```bash
sudo apt update
sudo apt install python3-serial
```

### 2. Download Scripts

**On PC:**
- `pc_baud_rate_sweep.py` (sender/controller)

**On Linux:**
- `rs485_listener_linux.py` (listener/responder)

---

## Running the Test

### Step 1: Start the Linux Listener

On the iMX8M Mini, run:
```bash
cd /home/CB2v4_validation/
python3 rs485_listener_linux.py
```

You should see:
```
============================================
RS485 Simple Listener
Linux/iMX8M Mini @ 9600 baud
============================================
Listening on RS485 at 9600 bps
Port: /dev/ttymxc0
Waiting for messages...

Starting up...
Ready!

.
```

The dots (`.`) indicate heartbeat - the listener is alive and waiting.

### Step 2: Run the PC Sender

On Windows, run:
```bash
python pc_baud_rate_sweep.py COM3
```

**Note:** Replace `COM3` with your actual COM port. Use Device Manager to find it.

The test will start:
```
Starting RS485 Adapter Baud Rate Sweep Test
Port: COM3
Baud rates: [9600, 19200, 38400, 57600, 115200]
Messages per rate: 100
Timeout: 2.0s

Overall Progress: 0.0% (1/5 baud rates)

============================================
Testing baud rate: 9600 bps
============================================
Sending baud change command: CHANGE_BAUD_9600

Progress: 100.0% (100/100)
Completed: 100/100 messages successful
Success Rate: 100.0%
BER: 0.00e+00
```

---

## Message Exchange Protocol

### Initial Setup (9600 baud)
Both devices start at 9600 baud:
- **PC (sender)**: Opens COM3 at 9600 baud
- **Linux (listener)**: Opens /dev/ttymxc0 at 9600 baud

---

### Test Sequence at 9600 Baud

#### 1. Baud Change Command (even if staying at 9600)

**PC sends:**
```
"CHANGE_BAUD_9600\n"
```

**Linux receives and responds:**
```
"ACK_BAUD_CHANGE\n"
```

**Linux console shows:**
```
0x43 0x48 0x41 0x4e 0x47 0x45 0x5f 0x42 0x41 0x55 0x44 0x5f 0x39 0x36 0x30 0x30 0x0a
[MSG #1] CHANGE_BAUD_9600
*** BAUD CHANGE REQUEST: 9600 -> 9600 ***
Sent ACK at 9600 baud
Switched to 9600 baud
```

#### 2. Test Messages (100 packets)

**PC sends test message #1:**
```
"RS485_TEST_MESSAGE_0000_a1b2c3d4\n"
```

Format breakdown:
- `RS485_TEST_MESSAGE_` - Base message identifier
- `0000` - Sequence number (4 digits, zero-padded)
- `a1b2c3d4` - MD5 checksum (first 8 hex digits)
- `\n` - Newline terminator

**Linux receives and echoes with ACK:**
```
"ACK_RS485_TEST_MESSAGE_0000_a1b2c3d4\n"
```

**Linux console shows:**
```
0x52 0x53 0x34 0x38 0x35 0x5f 0x54 0x45 0x53 0x54 0x5f 0x4d 0x45 0x53 0x53 0x41 0x47 0x45 0x5f 0x30 0x30 0x30 0x30 0x5f 0x61 0x31 0x62 0x32 0x63 0x33 0x64 0x34 0x0a
[MSG #2] RS485_TEST_MESSAGE_0000_a1b2c3d4
Sent ACK
```

**PC validates:** Checks that response starts with "ACK_" and matches sent message ✓

This repeats for messages #1-100 at 9600 baud.

---

### Switching to 19200 Baud

#### 1. PC sends baud change command (at current 9600 baud)

**PC → Linux:**
```
"CHANGE_BAUD_19200\n"
```

**Hex bytes:**
```
43 48 41 4E 47 45 5F 42 41 55 44 5F 31 39 32 30 30 0A
C  H  A  N  G  E  _  B  A  U  D  _  1  9  2  0  0  \n
```

#### 2. Linux responds at 9600 baud

**Linux → PC:**
```
"ACK_BAUD_CHANGE\n"
```

**Hex bytes:**
```
41 43 4B 5F 42 41 55 44 5F 43 48 41 4E 47 45 0A
A  C  K  _  B  A  U  D  _  C  H  A  N  G  E  \n
```

**Linux console shows:**
```
0x43 0x48 0x41 0x4e 0x47 0x45 0x5f 0x42 0x41 0x55 0x44 0x5f 0x31 0x39 0x32 0x30 0x30 0x0a
[MSG #101] CHANGE_BAUD_19200
*** BAUD CHANGE REQUEST: 9600 -> 19200 ***
Sent ACK at 9600 baud
Switched to 19200 baud
```

#### 3. Both sides switch baud rates

**Linux:**
- Closes serial port
- Reopens at 19200 baud
- Waits 0.2 seconds for hardware to stabilize

**PC:**
- Receives ACK at 9600 baud
- Changes baudrate to 19200
- Waits 0.5 seconds for both sides to stabilize

#### 4. Continue testing at 19200 baud

Now all communication happens at 19200 baud. The PC sends 100 test messages, Linux echoes them back.

**PC sends (at 19200 baud):**
```
"RS485_TEST_MESSAGE_0000_x7y8z9w0\n"
```

**Linux responds (at 19200 baud):**
```
"ACK_RS485_TEST_MESSAGE_0000_x7y8z9w0\n"
```

---

### Complete Test Sequence

The process repeats for all configured baud rates:

1. **9600 baud** → Send baud change command → 100 test messages
2. **19200 baud** → Send baud change command → 100 test messages
3. **38400 baud** → Send baud change command → 100 test messages
4. **57600 baud** → Send baud change command → 100 test messages
5. **115200 baud** → Send baud change command → 100 test messages

---

## Visual Timeline Example

**Single message exchange at 9600 baud:**

```
Time    PC (9600 baud)                          Linux (9600 baud)
────────────────────────────────────────────────────────────────────
0ms     Send: "CHANGE_BAUD_9600\n"
                                    →
2ms                                             Receive: "CHANGE_BAUD_9600"
3ms                                             Process command
4ms                                         ←   Send: "ACK_BAUD_CHANGE\n"
6ms     Receive: "ACK_BAUD_CHANGE"
7ms     ✓ Validated

50ms    Send: "RS485_TEST_MESSAGE_0000_a1b2c3d4\n"
                                    →
52ms                                            Receive test message
53ms                                        ←   Send: "ACK_RS485_TEST_MESSAGE_0000_a1b2c3d4\n"
55ms    Receive ACK
56ms    ✓ Validated (Success count: 1/100)

100ms   Send: "RS485_TEST_MESSAGE_0001_b2c3d4e5\n"
                                    →
102ms                                           Receive test message
103ms                                       ←   Send: "ACK_RS485_TEST_MESSAGE_0001_b2c3d4e5\n"
105ms   Receive ACK
106ms   ✓ Validated (Success count: 2/100)

...     (continues for remaining 98 messages)
```

**Baud rate change sequence:**

```
Time    PC (9600 baud)                          Linux (9600 baud)
────────────────────────────────────────────────────────────────────
0ms     Send: "CHANGE_BAUD_19200\n"
                                    →
2ms                                             Receive: "CHANGE_BAUD_19200"
3ms                                             Parse: new_baud = 19200
4ms                                         ←   Send: "ACK_BAUD_CHANGE\n" (at 9600)
6ms     Receive: "ACK_BAUD_CHANGE"
7ms     ✓ Baud change acknowledged

8ms                                             Close port
10ms                                            Reopen at 19200 baud
210ms                                           Ready at 19200 baud

500ms   Change baudrate to 19200
510ms   Wait for stabilization
800ms   Ready at 19200 baud

        Both sides now at 19200 baud ✓

850ms   Send: "RS485_TEST_MESSAGE_0000_x7y8z9w0\n" (at 19200)
                                    →
851ms                                           Receive (at 19200)
852ms                                       ←   Send: "ACK_..." (at 19200)
853ms   Receive ACK
854ms   ✓ Communication working at 19200!
```

---

## Expected Output

### Linux (Listener) Console

```
============================================
RS485 Simple Listener
Linux/iMX8M Mini @ 9600 baud
============================================
Listening on RS485 at 9600 bps
Port: /dev/ttymxc0
Waiting for messages...

Starting up...
Ready!

.0x43 0x48 0x41 0x4e 0x47 0x45 0x5f 0x42 0x41 0x55 0x44 0x5f 0x39 0x36 0x30 0x30 0x0a
[MSG #1] CHANGE_BAUD_9600
*** BAUD CHANGE REQUEST: 9600 -> 9600 ***
Sent ACK at 9600 baud
Switched to 9600 baud

.0x52 0x53 0x34 0x38 0x35 0x5f 0x54 0x45 0x53 0x54 0x5f 0x4d 0x45 0x53 0x53 0x41 0x47 0x45 0x5f 0x30 0x30 0x30 0x30 0x5f 0x61 0x31 0x62 0x32 0x63 0x33 0x64 0x34 0x0a
[MSG #2] RS485_TEST_MESSAGE_0000_a1b2c3d4
Sent ACK
.0x52 0x53 0x34 0x38 0x35 0x5f 0x54 0x45 0x53 0x54 0x5f 0x4d 0x45 0x53 0x53 0x41 0x47 0x45 0x5f 0x30 0x30 0x30 0x31 0x5f 0x62 0x32 0x63 0x33 0x64 0x34 0x65 0x35 0x0a
[MSG #3] RS485_TEST_MESSAGE_0001_b2c3d4e5
Sent ACK

... (100 messages at 9600 baud)

.0x43 0x48 0x41 0x4e 0x47 0x45 0x5f 0x42 0x41 0x55 0x44 0x5f 0x31 0x39 0x32 0x30 0x30 0x0a
[MSG #102] CHANGE_BAUD_19200
*** BAUD CHANGE REQUEST: 9600 -> 19200 ***
Sent ACK at 9600 baud
Switched to 19200 baud

... (100 messages at 19200 baud)

--- Status ---
Messages received: 505
Last activity: 0 seconds ago
Uptime: 120 seconds
-------------
```

### PC (Sender) Console

```
Starting RS485 Adapter Baud Rate Sweep Test
Port: COM3
Baud rates: [9600, 19200, 38400, 57600, 115200]
Messages per rate: 100
Timeout: 2.0s

Opening serial port at 9600 bps...
Serial port opened successfully


Overall Progress: 0.0% (1/5 baud rates)

============================================
Testing baud rate: 9600 bps
============================================
Sending baud change command: CHANGE_BAUD_9600
Baud change acknowledged by ESP32

Progress: 100.0% (100/100)
Completed: 100/100 messages successful
Success Rate: 100.0%
BER: 0.00e+00


Overall Progress: 20.0% (2/5 baud rates)

============================================
Testing baud rate: 19200 bps
============================================
Sending baud change command: CHANGE_BAUD_19200
Baud change acknowledged by ESP32

Progress: 100.0% (100/100)
Completed: 100/100 messages successful
Success Rate: 100.0%
BER: 0.00e+00


Overall Progress: 40.0% (3/5 baud rates)

============================================
Testing baud rate: 38400 bps
============================================
...


============================================
TEST COMPLETED!
============================================
Reports saved:
  JSON: rs485_baud_sweep_report_20251014_143055.json
  Text: rs485_baud_sweep_report_20251014_143055.txt

Overall Success Rate: 100.0%
Best Baud Rate: 115200 bps (100.0% success)
Worst Baud Rate: 9600 bps (100.0% success)
```

---

## Test Results

After the test completes, two report files are generated on the PC:

### JSON Report
**Filename:** `rs485_baud_sweep_report_YYYYMMDD_HHMMSS.json`

Contains:
- Test metadata (start time, duration, port, etc.)
- Detailed results for each baud rate
- Success/failure counts
- Bit error rates (BER)
- Average response times
- Error messages (if any)

### Text Report
**Filename:** `rs485_baud_sweep_report_YYYYMMDD_HHMMSS.txt`

Human-readable summary with:
- Overall success rate
- Best and worst performing baud rates
- Detailed statistics per baud rate
- First 10 errors (if any occurred)

---

## Interpreting Results

### Success Metrics

**100% Success Rate:**
- All 100 messages received correctly at this baud rate
- RS485 communication is reliable at this speed
- ✓ PASS

**90-99% Success Rate:**
- Some packet loss occurred
- May indicate marginal signal quality
- ⚠️ WARNING - Check cabling, termination, ground

**< 90% Success Rate:**
- Significant communication issues
- Not suitable for production use at this baud rate
- ✗ FAIL - Check hardware setup

### Bit Error Rate (BER)

**BER = 0.00e+00:**
- No bit errors detected
- Perfect communication
- ✓ EXCELLENT

**BER < 1.00e-06:**
- Very few bit errors
- Acceptable for most applications
- ✓ GOOD

**BER > 1.00e-04:**
- Significant bit corruption
- Investigate signal integrity issues
- ✗ POOR

### Response Time

**< 50 ms:**
- Fast communication
- ✓ EXCELLENT

**50-100 ms:**
- Normal response time
- ✓ GOOD

**> 200 ms:**
- Slow response (may indicate timeout retries)
- ⚠️ Investigate delays

---

## Troubleshooting

### Test Won't Start

**Problem:** Linux listener shows no activity

**Solutions:**
1. Check RS485 physical connections (A+, B-, GND)
2. Verify port name: `ls -la /dev/ttymxc*`
3. Check permissions: `sudo chmod 666 /dev/ttymxc0`
4. Test loopback: Connect A+ to B- on Linux side, run sender on Linux

**Problem:** PC can't open COM port

**Solutions:**
1. Check Device Manager for correct COM port number
2. Close any other programs using the port (PuTTY, Arduino IDE, etc.)
3. Verify RS485 adapter is detected: Check Device Manager → Ports

### Baud Change Fails

**Problem:** "Baud change command failed" error

**Solutions:**
1. Linux listener not running or not responding
2. Check RS485 cable connections
3. Verify both devices on same initial baud rate (9600)
4. Check for RS485 termination resistors if cables are long

### High Packet Loss

**Problem:** Success rate < 90%

**Solutions:**
1. **Check termination:** RS485 needs 120Ω termination resistors at both ends
2. **Reduce cable length:** Try shorter cable first
3. **Check ground connection:** Ensure common ground between devices
4. **Lower baud rate:** Test at 9600 to rule out speed issues
5. **Check power supply:** Ensure stable power to both devices

### Timeouts

**Problem:** Many timeout errors

**Solutions:**
1. Linux listener crashed or stopped - restart it
2. RS485 cable disconnected
3. Wrong baud rate mismatch
4. Increase timeout: Edit `pc_baud_rate_sweep.py`, change `timeout=2.0` to `timeout=5.0`

---

## Advanced Usage

### Test Specific Baud Rates Only

Edit `pc_baud_rate_sweep.py` line 21:
```python
# Test only specific baud rates
BAUD_RATES = [9600, 115200]  # Only test 9600 and 115200
```

### Change Number of Test Messages

Edit `pc_baud_rate_sweep.py` or use command line:
```bash
python pc_baud_rate_sweep.py COM3 --messages 1000
```

### Change Timeout

```bash
python pc_baud_rate_sweep.py COM3 --timeout 5.0
```

### Start at Different Baud Rate

Edit both scripts to use same starting baud rate:

**pc_baud_rate_sweep.py:**
```python
first_baud = 115200  # Start at 115200 instead of 9600
```

**rs485_listener_linux.py:**
```python
BAUD_RATE = 115200  # Start at 115200 instead of 9600
```

Or use command line on Linux:
```bash
python3 rs485_listener_linux.py --baud 115200
```

---

## Safety Notes

1. **Stop PC sender before stopping Linux listener** - Otherwise PC may report failures
2. **Wait 2 seconds between tests** - Allow hardware to stabilize
3. **Don't hot-plug RS485 cables** - May damage transceivers
4. **Use proper RS485 termination** - 120Ω at both ends for long cables
5. **Ground both devices** - Share common ground reference

---

## Files Required

### On PC (Windows)
- `pc_baud_rate_sweep.py` - Sender/controller script
- Python 3.7+ with pyserial installed

### On Linux (iMX8M Mini)
- `rs485_listener_linux.py` - Listener/responder script
- Python 3 with python3-serial installed

---

## Quick Start Checklist

- [ ] Install Python dependencies on both systems
- [ ] Connect RS485 cables (A+, B-, GND)
- [ ] Verify Linux UART port exists: `ls -la /dev/ttymxc0`
- [ ] Verify PC COM port in Device Manager
- [ ] Start Linux listener: `python3 rs485_listener_linux.py`
- [ ] Start PC sender: `python pc_baud_rate_sweep.py COM3`
- [ ] Wait for test to complete (~10 minutes for 500 messages)
- [ ] Review generated reports
- [ ] Check success rates and BER values

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Linux console output for error messages
3. Check PC reports for detailed failure information
4. Verify hardware connections with multimeter
5. Test with loopback (A+ to B-) to isolate sender/receiver issues

---

**Last Updated:** 2025-10-14
**Version:** 1.0
**Platform:** Toradex Verdin iMX8M Mini + Windows PC
