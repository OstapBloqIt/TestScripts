# RS485 Half-Duplex Fixes

## Critical Changes Made

### ✅ Fixed Half-Duplex RS485 Communication

RS485 is **half-duplex** - devices cannot transmit and receive simultaneously. The scripts now properly handle this with:

#### 1. Transmission Timing
```python
# Before sending, wait for any incoming transmission to finish
time.sleep(RS485_TURNAROUND_DELAY)  # 50ms turnaround time

# Send data
ser.write(data)
ser.flush()

# Calculate how long transmission takes
bytes_sent = len(data)
tx_time = (bytes_sent * 10) / baudrate  # 10 bits per byte (start + 8 data + stop)

# Wait for transmission to complete before switching to receive
time.sleep(tx_time)
```

#### 2. Buffer Management
```python
# ALWAYS clear buffers before critical operations
ser.reset_input_buffer()   # Clear RX buffer
ser.reset_output_buffer()  # Clear TX buffer
```

#### 3. Baud Negotiation Retry Logic
If baud rate negotiation fails:
- **Clears all buffers** (input and output)
- **Retries up to 3 times** automatically
- **Waits 100ms between retries** to let the bus settle

### Configuration Constants

```python
RS485_TURNAROUND_DELAY = 0.05      # 50ms turnaround time
BAUD_NEGOTIATION_RETRIES = 3       # 3 retry attempts
BAUD_SYNC_DELAY = 0.5              # 500ms delay after baud change
```

## Why This Matters

### ❌ Before (WRONG - Full Duplex Assumption)
```python
# WRONG: Trying to receive immediately after sending
ser.write(command)
response = ser.read()  # FAILS! Still transmitting!
```

### ✅ After (CORRECT - Half Duplex)
```python
# CORRECT: Wait for transmission to finish
ser.write(command)
ser.flush()

# Calculate transmission time
tx_time = (len(command) * 10) / baudrate
time.sleep(tx_time + RS485_TURNAROUND_DELAY)

# NOW we can receive
response = ser.read()
```

## Timing Diagram

```
Half-Duplex RS485 Bus (Only ONE direction at a time!)
====================================================

Time    Sender                     Echo Server
----    ------                     -----------
0ms     TX: "BAUD_CHANGE_19200"
        (transmitting...)
15ms    [TX complete]
        [wait turnaround]
65ms                               RX: received command
        [waiting for response]     [wait turnaround]
115ms                              TX: "BAUD_ACK_19200"
                                   (transmitting...)
125ms   RX: "BAUD_ACK_19200"       [TX complete]
        ✓ Success!                 [wait for ACK TX to finish]
175ms   [switch baud rate]         [switch baud rate]
====================================================
```

## Key Points

1. **Never transmit while receiving** - Wait for turnaround delay
2. **Always calculate TX time** - Don't assume transmission is instant
3. **Clear buffers on failure** - Prevent corrupted data from retries
4. **Retry automatically** - Handle transient errors gracefully

## Testing the Fixes

Run the test exactly as before:

**Linux (Echo Server):**
```bash
python3 rs485_test_linux.py /dev/ttymxc0 --mode auto-sync
```

**Windows (Sender):**
```powershell
python rs485_test_windows.py COM3 --mode sender
```

You should now see:
- ✅ Successful baud rate negotiations
- ✅ No "No ACK received" errors
- ✅ Reliable communication at all baud rates
- ✅ Automatic retry on transient failures

## Transmission Time Examples

At 9600 baud:
- 1 byte = (1 × 10 bits) / 9600 = 1.04 ms
- 20 bytes = (20 × 10 bits) / 9600 = 20.8 ms

At 115200 baud:
- 1 byte = (1 × 10 bits) / 115200 = 0.087 ms
- 20 bytes = (20 × 10 bits) / 115200 = 1.74 ms

**Always add 50ms turnaround delay** for RS485 transceiver switching!

## What Changed in Each Script

### Both Linux and Windows Scripts:

1. **Added half-duplex timing constants**
2. **Updated `send_baud_change_command()`:**
   - Clears buffers before sending
   - Calculates transmission time
   - Waits for TX to complete before RX
   - Retries up to 3 times on failure
   - Clears buffers between retries

3. **Updated echo server auto-sync mode:**
   - Waits for turnaround before responding
   - Calculates ACK transmission time
   - Waits for ACK TX to complete
   - Clears buffers before baud switch

4. **Updated regular echo mode:**
   - Waits for turnaround before echoing
   - Calculates echo transmission time
   - Proper half-duplex timing

## Common Issues Fixed

### Issue 1: "No ACK received"
**Cause:** Trying to receive while still transmitting (half-duplex violation)
**Fixed:** Calculate TX time and wait before receiving

### Issue 2: Corrupted data on retry
**Cause:** Old data in buffers from failed attempts
**Fixed:** Clear both input and output buffers before retry

### Issue 3: Intermittent failures
**Cause:** Timing issues with half-duplex
**Fixed:** Proper turnaround delays and calculated TX times

### Issue 4: Bus collisions
**Cause:** Both sides trying to transmit simultaneously
**Fixed:** Sender transmits first, waits, then echo responds

## Verification

You can verify the fixes are working by observing:

1. **Sender logs show:**
   ```
   Sending baud change command: BAUD_CHANGE_19200
   ✓ Received ACK: BAUD_ACK_19200
   ```

2. **Echo server logs show:**
   ```
   *** BAUD CHANGE REQUEST: 9600 -> 19200 ***
   Sent ACK at 9600 baud
   Switched to 19200 baud
   ```

3. **No retry messages** (unless there's actual line noise/errors)

4. **100% success rate** on all baud rates

---

## Summary

The scripts now properly implement **half-duplex RS485 communication** with:
- ✅ Calculated transmission times
- ✅ Proper turnaround delays
- ✅ Buffer management
- ✅ Automatic retry with buffer clearing
- ✅ No full-duplex assumptions

This ensures reliable communication even at high baud rates and with varying cable lengths.
