#!/usr/bin/env python3
"""
RS485 Data Integrity Test - PC Side
Tests SP3485EN adapter by sending data patterns and calculating BER
"""

import serial
import time
import sys
import random
from enum import Enum

class DataPattern(Enum):
    SEQUENTIAL = 1      # 0x00, 0x01, 0x02, ..., 0xFF, 0x00, ...
    ALTERNATING = 2     # 0xAA, 0x55, 0xAA, 0x55, ...
    ALL_ZEROS = 3       # 0x00, 0x00, 0x00, ...
    ALL_ONES = 4        # 0xFF, 0xFF, 0xFF, ...
    RANDOM = 5          # Random bytes with fixed seed
    WALKING_ONES = 6    # 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80
    WALKING_ZEROS = 7   # 0xFE, 0xFD, 0xFB, 0xF7, 0xEF, 0xDF, 0xBF, 0x7F
    PRBS = 8           # Pseudo-random binary sequence

def generate_pattern(pattern_type, length, seed=12345):
    """Generate test data pattern"""
    data = bytearray(length)

    if pattern_type == DataPattern.SEQUENTIAL:
        for i in range(length):
            data[i] = i % 256

    elif pattern_type == DataPattern.ALTERNATING:
        for i in range(length):
            data[i] = 0xAA if i % 2 == 0 else 0x55

    elif pattern_type == DataPattern.ALL_ZEROS:
        data = bytearray(length)  # Already zeros

    elif pattern_type == DataPattern.ALL_ONES:
        for i in range(length):
            data[i] = 0xFF

    elif pattern_type == DataPattern.RANDOM:
        random.seed(seed)
        for i in range(length):
            data[i] = random.randint(0, 255)

    elif pattern_type == DataPattern.WALKING_ONES:
        for i in range(length):
            data[i] = 1 << (i % 8)

    elif pattern_type == DataPattern.WALKING_ZEROS:
        for i in range(length):
            data[i] = ~(1 << (i % 8)) & 0xFF

    elif pattern_type == DataPattern.PRBS:
        # PRBS-7 polynomial: x^7 + x^6 + 1
        lfsr = seed & 0x7F
        for i in range(length):
            byte_val = 0
            for bit in range(8):
                byte_val = (byte_val << 1) | (lfsr & 1)
                new_bit = ((lfsr >> 6) ^ (lfsr >> 5)) & 1
                lfsr = ((lfsr >> 1) | (new_bit << 6)) & 0x7F
            data[i] = byte_val

    return bytes(data)

def calculate_ber(sent_data, received_data):
    """Calculate bit error rate"""
    if len(sent_data) != len(received_data):
        print(f"WARNING: Length mismatch! Sent: {len(sent_data)}, Received: {len(received_data)}")
        min_len = min(len(sent_data), len(received_data))
        sent_data = sent_data[:min_len]
        received_data = received_data[:min_len]

    bit_errors = 0
    byte_errors = 0
    total_bits = len(sent_data) * 8

    error_positions = []

    for i in range(len(sent_data)):
        if sent_data[i] != received_data[i]:
            byte_errors += 1
            xor = sent_data[i] ^ received_data[i]
            # Count bit differences
            bits = bin(xor).count('1')
            bit_errors += bits
            error_positions.append({
                'index': i,
                'sent': sent_data[i],
                'received': received_data[i],
                'bits_wrong': bits
            })

    ber = bit_errors / total_bits if total_bits > 0 else 0
    byte_error_rate = byte_errors / len(sent_data) if len(sent_data) > 0 else 0

    return {
        'bit_errors': bit_errors,
        'byte_errors': byte_errors,
        'total_bits': total_bits,
        'total_bytes': len(sent_data),
        'ber': ber,
        'byte_error_rate': byte_error_rate,
        'error_positions': error_positions
    }

def print_pattern_menu():
    """Display pattern selection menu"""
    print("\n" + "="*60)
    print("RS485 Data Integrity Test - Pattern Selection")
    print("="*60)
    print("1. Sequential    (0x00, 0x01, 0x02, ..., 0xFF)")
    print("2. Alternating   (0xAA, 0x55, 0xAA, 0x55, ...)")
    print("3. All Zeros     (0x00, 0x00, 0x00, ...)")
    print("4. All Ones      (0xFF, 0xFF, 0xFF, ...)")
    print("5. Random        (Pseudo-random with seed)")
    print("6. Walking Ones  (0x01, 0x02, 0x04, 0x08, ...)")
    print("7. Walking Zeros (0xFE, 0xFD, 0xFB, 0xF7, ...)")
    print("8. PRBS-7        (Pseudo-random binary sequence)")
    print("="*60)

def main():
    # Configuration
    BAUD_RATE = 9600
    DATA_LENGTH = 1000

    # Prompt for COM port
    print("\nRS485 Adapter Data Integrity Test")
    print("-" * 40)
    port = input("Enter COM port (e.g., COM3): ").strip()

    # Pattern selection
    print_pattern_menu()

    while True:
        try:
            choice = int(input("\nSelect pattern (1-8): "))
            if 1 <= choice <= 8:
                pattern_type = DataPattern(choice)
                break
            else:
                print("Invalid choice. Please select 1-8.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Optional seed for random/PRBS patterns
    seed = 12345
    if pattern_type in [DataPattern.RANDOM, DataPattern.PRBS]:
        seed_input = input(f"Enter seed (default: {seed}): ").strip()
        if seed_input:
            try:
                seed = int(seed_input)
            except ValueError:
                print(f"Invalid seed, using default: {seed}")

    # Generate test pattern
    print(f"\nGenerating {DATA_LENGTH} bytes of {pattern_type.name} pattern...")
    test_data = generate_pattern(pattern_type, DATA_LENGTH, seed)

    # Open serial port
    print(f"Opening {port} at {BAUD_RATE} bps...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=5
        )
        time.sleep(2)  # Wait for port to stabilize
        ser.reset_input_buffer()
        ser.reset_output_buffer()

    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("Starting Data Integrity Test")
    print("="*60)
    print(f"Pattern:      {pattern_type.name}")
    print(f"Data Length:  {DATA_LENGTH} bytes")
    print(f"Baud Rate:    {BAUD_RATE} bps")
    print(f"Seed:         {seed}" if pattern_type in [DataPattern.RANDOM, DataPattern.PRBS] else "")
    print("="*60)

    # Send data
    print(f"\nSending {len(test_data)} bytes...")
    start_time = time.time()
    bytes_written = ser.write(test_data)
    ser.flush()

    # Calculate expected duration
    bits_per_byte = 10  # 1 start + 8 data + 1 stop
    expected_duration = (DATA_LENGTH * bits_per_byte) / BAUD_RATE
    print(f"Sent {bytes_written} bytes")
    print(f"Expected transmission time: {expected_duration:.2f} seconds")

    # Receive echo data
    print("\nWaiting for echo from ESP32...")
    received_data = bytearray()
    receive_start = time.time()
    timeout = expected_duration + 10  # Extra time for processing

    while len(received_data) < DATA_LENGTH:
        if time.time() - receive_start > timeout:
            print(f"\nTIMEOUT: Only received {len(received_data)}/{DATA_LENGTH} bytes")
            break

        if ser.in_waiting > 0:
            chunk = ser.read(ser.in_waiting)
            received_data.extend(chunk)
            print(f"\rReceived: {len(received_data)}/{DATA_LENGTH} bytes", end='', flush=True)

    end_time = time.time()
    total_time = end_time - start_time

    print(f"\n\nTest completed in {total_time:.2f} seconds")

    # Calculate BER
    print("\n" + "="*60)
    print("Analyzing Results")
    print("="*60)

    results = calculate_ber(test_data, bytes(received_data))

    print(f"Total Bytes:      {results['total_bytes']}")
    print(f"Total Bits:       {results['total_bits']}")
    print(f"Byte Errors:      {results['byte_errors']}")
    print(f"Bit Errors:       {results['bit_errors']}")
    print(f"Byte Error Rate:  {results['byte_error_rate']*100:.6f}%")
    print(f"Bit Error Rate:   {results['ber']*100:.9f}%")

    if results['bit_errors'] == 0:
        print("\n✓ SUCCESS: No errors detected!")
    else:
        print(f"\n✗ FAILURE: {results['bit_errors']} bit errors detected")

        # Show first 10 errors
        print("\nFirst errors (up to 10):")
        for i, err in enumerate(results['error_positions'][:10]):
            print(f"  [{err['index']:04d}] Sent: 0x{err['sent']:02X}, "
                  f"Received: 0x{err['received']:02X}, "
                  f"Bits wrong: {err['bits_wrong']}")

    print("="*60)

    ser.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
