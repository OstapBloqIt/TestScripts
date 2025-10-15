# RS485 Test - Quick Start Guide

## Automatic Baud Rate Synchronization

Both scripts now support **automatic baud rate synchronization**! The sender and echo server start at 9600 baud, then the sender sends special commands to switch baud rates automatically.

## Protocol

1. **Both sides start at 9600 baud**
2. **Sender sends**: `BAUD_CHANGE_<new_baudrate>` (e.g., `BAUD_CHANGE_115200`)
3. **Echo server responds**: `BAUD_ACK_<new_baudrate>` at current baud rate
4. **Both sides switch** to the new baud rate
5. **Testing begins** at the new baud rate

---

## Windows Initiates Test (Recommended)

### Step 1: Start Linux Echo Server (Auto-Sync Mode)
```bash
# On iMX8M Mini
python3 /tmp/TestScripts/Kerong/rs485_test_linux.py /dev/ttymxc1 --mode auto-sync
```

### Step 2: Run Windows Sender
```powershell
# On Windows PC
python rs485_test_windows.py COM3 --mode sender
```

That's it! The test will automatically:
- Start at 9600 baud
- Test 9600, then send baud change command
- Test 19200, then send baud change command
- Test 38400, then send baud change command
- Test 57600, then send baud change command
- Test 115200
- Display complete results

---

## Linux Initiates Test

### Step 1: Start Windows Echo Server (Auto-Sync Mode)
```powershell
# On Windows PC
python rs485_test_windows.py COM3 --mode auto-sync
```

### Step 2: Run Linux Sender
```bash
# On iMX8M Mini
python3 /tmp/TestScripts/Kerong/rs485_test_linux.py /dev/ttymxc0 --mode sender
```

---

## Expected Output

### Echo Server (Auto-Sync Mode)
```
============================================================
Echo Server Mode - Auto-Sync
============================================================
Starting at 9600 baud
Will automatically sync to baud rate changes
============================================================

Listening for data on /dev/ttymxc0...
Press Ctrl+C to stop

[12:34:56.123] Received #1: RS485_TEST_PACKET_9600_001
[12:34:56.234] Received #2: RS485_TEST_PACKET_9600_002
...

[12:35:10.456] *** BAUD CHANGE REQUEST: 9600 -> 19200 ***
[12:35:10.456] Sent ACK at 9600 baud
[12:35:10.567] Switched to 19200 baud

[12:35:11.123] Received #11: RS485_TEST_PACKET_19200_001
...
```

### Sender Mode
```
============================================================
RS485 Communication Test Suite - Linux (Sender Mode)
============================================================
Port: /dev/ttymxc0
Starting baud rate: 9600
Baud rates to test: 9600, 19200, 38400, 57600, 115200
Packets per test: 10
============================================================
IMPORTANT: Echo server should be running in 'auto-sync' mode!
============================================================

--- Testing Baud Rate: 9600 ---
Testing at 9600 baud...
  ✓ Packet 1/10: OK (RTT: 45.23 ms)
  ✓ Packet 2/10: OK (RTT: 44.89 ms)
  ...

Results for 9600 baud:
  Success: 10/10 (100.0%)
  Failed:  0/10
  Avg RTT: 45.15 ms

--- Testing Baud Rate: 19200 ---
  Sending baud change command: BAUD_CHANGE_19200
  ✓ Received ACK: BAUD_ACK_19200
Testing at 19200 baud...
  ✓ Packet 1/10: OK (RTT: 24.12 ms)
  ...
```

---

## Command Reference

### Linux Commands
```bash
# Auto-sync echo server (RECOMMENDED)
python3 rs485_test_linux.py /dev/ttymxc0 --mode auto-sync

# Sender mode (tests all baud rates)
python3 rs485_test_linux.py /dev/ttymxc0 --mode sender

# Fixed baud rate echo server
python3 rs485_test_linux.py /dev/ttymxc0 --mode echo --baud 115200
```

### Windows Commands
```powershell
# List available COM ports
python rs485_test_windows.py --list

# Auto-sync echo server (RECOMMENDED)
python rs485_test_windows.py COM3 --mode auto-sync

# Sender mode (tests all baud rates)
python rs485_test_windows.py COM3 --mode sender

# Fixed baud rate echo server
python rs485_test_windows.py COM3 --mode echo --baud 115200
```

---

## Troubleshooting

### Problem: "No ACK received"
- **Cause**: Echo server not running or not in auto-sync mode
- **Solution**: Make sure echo server is running with `--mode auto-sync`

### Problem: Tests timeout after first baud rate
- **Cause**: Echo server didn't switch baud rates
- **Solution**:
  - Check echo server logs for baud change messages
  - Verify both scripts have the same `BAUD_RATES` list
  - Make sure echo server received the BAUD_CHANGE command

### Problem: "Device disconnected" or "Port not found"
- **Linux**: Check `/dev/ttymxc0` exists: `ls -l /dev/ttymxc0`
- **Windows**: Check Device Manager for COM port number
- **Solution**: Use `--list` option to see available ports

---

## How It Works

The synchronization protocol ensures both sides are always at the same baud rate:

```
Time    Sender (9600)              Echo Server (9600)
====    =================          ==================
0ms     Send: "BAUD_CHANGE_19200"
10ms                               Receive command
11ms                               Send: "BAUD_ACK_19200"
12ms    Receive ACK
100ms   Switch to 19200            Switch to 19200
====    =================          ==================
        Sender (19200)             Echo Server (19200)
1100ms  Send test packet
1112ms                             Echo test packet back
1124ms  Receive echo
```

This ensures:
- ✅ No manual baud rate coordination needed
- ✅ Automatic synchronization
- ✅ Both sides always in sync
- ✅ Clean transition between rates

---

## Tips

1. **Always use auto-sync mode** for multi-baud testing
2. **Start echo server first**, then start sender
3. **Check both terminals** - you'll see the synchronization happening
4. **Use fixed echo mode** only for single baud rate testing
5. **Test lower baud rates first** (9600) to verify connection

---

## Next Steps

After successful testing:
1. Review the test summary to find the best baud rate
2. Check for any packet loss or high latency
3. Use the optimal baud rate in your application
4. Implement proper error handling based on observed patterns

Good luck with your RS485 testing!
