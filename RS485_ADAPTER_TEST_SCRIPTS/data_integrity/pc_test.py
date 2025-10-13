#!/usr/bin/env python3
"""
RS485 Data Integrity Test - PC Side
Tests SP3485EN adapter by sending data patterns and calculating BER
"""

import serial
import time
import sys
import random
import json
from datetime import datetime
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
    print("9. Run ALL patterns sequentially")
    print("10. Run ALL patterns + ALL baud rates")
    print("="*60)

# Common baud rates for RS485 testing
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]

def negotiate_baud_rate(ser, new_baud):
    """Negotiate baud rate change with ESP32"""
    print(f"\n>>> Negotiating baud rate change to {new_baud}...")

    # Send baud rate change command
    command = f"BAUD:{new_baud}\n"
    ser.write(command.encode('utf-8'))
    ser.flush()

    print(f"Sent: {command.strip()}")

    # Wait for ACK
    ack_timeout = 2.0
    ack_start = time.time()
    ack_response = ""

    while time.time() - ack_start < ack_timeout:
        if ser.in_waiting > 0:
            char = ser.read(1).decode('utf-8', errors='ignore')
            ack_response += char
            if char == '\n':
                break
        time.sleep(0.01)

    ack_response = ack_response.strip()
    print(f"Received: {ack_response}")

    if ack_response == f"ACK:{new_baud}":
        print(f"✓ ESP32 acknowledged baud change")

        # Wait a bit for ESP32 to switch
        time.sleep(0.2)

        # Close and reopen port at new baud rate
        port_name = ser.port
        ser.close()
        time.sleep(0.1)

        print(f"Switching PC to {new_baud} baud...")
        ser = serial.Serial(
            port=port_name,
            baudrate=new_baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=5
        )
        time.sleep(0.5)

        # Verify connection with TEST command
        print(f"Verifying connection at {new_baud} baud...")
        ser.write(b"TEST\n")
        ser.flush()

        test_response = ""
        test_timeout = 2.0
        test_start = time.time()

        while time.time() - test_start < test_timeout:
            if ser.in_waiting > 0:
                char = ser.read(1).decode('utf-8', errors='ignore')
                test_response += char
                if char == '\n':
                    break
            time.sleep(0.01)

        test_response = test_response.strip()
        print(f"Received: {test_response}")

        if test_response == "OK":
            print(f"✓ Baud rate successfully changed to {new_baud}!")
            return ser
        else:
            print(f"✗ Verification failed at {new_baud} baud")
            return None
    else:
        print(f"✗ ESP32 did not acknowledge baud change")
        return None

def run_single_test(ser, pattern_type, data_length, baud_rate, seed=12345):
    """Run a single test - NUCLEAR MODE: Send all, wait, receive all"""
    # Generate test pattern
    print(f"\nGenerating {data_length} bytes of {pattern_type.name} pattern...")
    test_data = generate_pattern(pattern_type, data_length, seed)

    print("\n" + "="*60)
    print(f"Testing Pattern: {pattern_type.name}")
    print("="*60)
    print(f"Data Length:  {data_length} bytes")
    print(f"Baud Rate:    {baud_rate} bps")
    if pattern_type in [DataPattern.RANDOM, DataPattern.PRBS]:
        print(f"Seed:         {seed}")
    print("="*60)

    # Clear buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.5)

    print(f"\nNUCLEAR MODE: Send all {data_length} bytes, then receive all {data_length} bytes")
    print(f"First 16 bytes to send: {' '.join(f'{b:02X}' for b in test_data[:16])}")

    start_time = time.time()
    bits_per_byte = 10  # 1 start + 8 data + 1 stop
    tx_time = (data_length * bits_per_byte) / baud_rate

    # STEP 1: Send ALL data
    print(f"\n>>> Sending all {data_length} bytes...")
    bytes_written = ser.write(test_data)
    ser.flush()
    print(f"Sent {bytes_written} bytes")
    print(f"Transmission time: ~{tx_time:.2f} seconds")

    # STEP 2: Wait for transmission to complete + ESP32 to buffer it
    print(f"\n>>> Waiting for ESP32 to buffer all data...")
    # Wait for: TX complete + ESP32 buffering + ESP32 delay (500ms) + ESP32 extra (100ms) + margin
    wait_time = tx_time + 0.5 + 0.1 + 0.2  # TX + ESP32 buffer wait + ESP32 delay + margin
    time.sleep(wait_time)
    print(f"Waited {wait_time:.2f} seconds")

    # STEP 3: Wait for ESP32 to transmit echo back
    print(f"\n>>> Waiting for ESP32 echo (expected {data_length} bytes)...")
    received_data = bytearray()
    rx_start = time.time()
    timeout = tx_time + 5.0  # RX should take same time as TX + margin

    while len(received_data) < data_length:
        elapsed = time.time() - rx_start

        if elapsed > timeout:
            print(f"\nTIMEOUT after {elapsed:.2f}s: Received {len(received_data)}/{data_length} bytes")
            break

        if ser.in_waiting > 0:
            chunk = ser.read(ser.in_waiting)
            received_data.extend(chunk)
            print(f"\rReceived: {len(received_data)}/{data_length} bytes", end='', flush=True)

        time.sleep(0.01)

    end_time = time.time()
    total_time = end_time - start_time

    print(f"\n\n>>> Test completed in {total_time:.2f} seconds")

    # Calculate BER
    print("\n" + "="*60)
    print("Results")
    print("="*60)

    results = calculate_ber(test_data, bytes(received_data))
    results['pattern'] = pattern_type.name
    results['data_length'] = data_length
    results['baud_rate'] = baud_rate
    results['seed'] = seed if pattern_type in [DataPattern.RANDOM, DataPattern.PRBS] else None
    results['test_duration'] = total_time
    results['throughput_bps'] = (len(received_data) * 8) / total_time if total_time > 0 else 0
    results['bytes_sent'] = bytes_written
    results['bytes_received'] = len(received_data)

    print(f"Total Bytes Sent:     {results['bytes_sent']}")
    print(f"Total Bytes Received: {results['bytes_received']}")
    print(f"Total Bits:           {results['total_bits']}")
    print(f"Byte Errors:          {results['byte_errors']}")
    print(f"Bit Errors:           {results['bit_errors']}")
    print(f"Byte Error Rate:      {results['byte_error_rate']*100:.6f}%")
    print(f"Bit Error Rate:       {results['ber']*100:.9f}%")
    print(f"Test Duration:        {results['test_duration']:.2f} seconds")
    print(f"Throughput:           {results['throughput_bps']:.2f} bps")

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

    return results

def save_results(test_results, port, baud_rate):
    """Save test results to JSON and text files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Prepare summary data
    summary = {
        'test_date': datetime.now().isoformat(),
        'port': port,
        'baud_rate': baud_rate,
        'total_tests': len(test_results),
        'tests_passed': sum(1 for r in test_results if r['bit_errors'] == 0),
        'tests_failed': sum(1 for r in test_results if r['bit_errors'] > 0),
        'total_bytes_sent': sum(r['bytes_sent'] for r in test_results),
        'total_bytes_received': sum(r['bytes_received'] for r in test_results),
        'total_bit_errors': sum(r['bit_errors'] for r in test_results),
        'total_byte_errors': sum(r['byte_errors'] for r in test_results),
        'test_results': []
    }

    # Add individual test results (without error_positions to keep file size manageable)
    for result in test_results:
        test_summary = {k: v for k, v in result.items() if k != 'error_positions'}
        test_summary['error_count'] = len(result['error_positions'])
        summary['test_results'].append(test_summary)

    # Save JSON report
    json_filename = f"rs485_integrity_test_{timestamp}.json"
    with open(json_filename, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nJSON report saved: {json_filename}")

    # Save text report
    txt_filename = f"rs485_integrity_test_{timestamp}.txt"
    with open(txt_filename, 'w') as f:
        f.write("="*70 + "\n")
        f.write("RS485 Data Integrity Test Report\n")
        f.write("="*70 + "\n")
        f.write(f"Test Date:            {summary['test_date']}\n")
        f.write(f"COM Port:             {port}\n")
        f.write(f"Baud Rate:            {baud_rate} bps\n")
        f.write(f"Total Tests:          {summary['total_tests']}\n")
        f.write(f"Tests Passed:         {summary['tests_passed']}\n")
        f.write(f"Tests Failed:         {summary['tests_failed']}\n")
        f.write(f"Total Bytes Sent:     {summary['total_bytes_sent']}\n")
        f.write(f"Total Bytes Received: {summary['total_bytes_received']}\n")
        f.write(f"Total Bit Errors:     {summary['total_bit_errors']}\n")
        f.write(f"Total Byte Errors:    {summary['total_byte_errors']}\n")
        f.write("="*70 + "\n\n")

        f.write("Individual Test Results:\n")
        f.write("="*70 + "\n")

        for i, result in enumerate(test_results, 1):
            f.write(f"\nTest {i}: {result['pattern']}\n")
            f.write("-"*70 + "\n")
            f.write(f"  Data Length:      {result['data_length']} bytes\n")
            f.write(f"  Bytes Sent:       {result['bytes_sent']}\n")
            f.write(f"  Bytes Received:   {result['bytes_received']}\n")
            f.write(f"  Bit Errors:       {result['bit_errors']}\n")
            f.write(f"  Byte Errors:      {result['byte_errors']}\n")
            f.write(f"  Bit Error Rate:   {result['ber']*100:.9f}%\n")
            f.write(f"  Byte Error Rate:  {result['byte_error_rate']*100:.6f}%\n")
            f.write(f"  Test Duration:    {result['test_duration']:.2f} seconds\n")
            f.write(f"  Throughput:       {result['throughput_bps']:.2f} bps\n")
            f.write(f"  Status:           {'PASS' if result['bit_errors'] == 0 else 'FAIL'}\n")

            if result['seed'] is not None:
                f.write(f"  Seed:             {result['seed']}\n")

            if result['error_positions']:
                f.write(f"\n  First Errors (up to 10):\n")
                for err in result['error_positions'][:10]:
                    f.write(f"    [{err['index']:04d}] Sent: 0x{err['sent']:02X}, "
                           f"Received: 0x{err['received']:02X}, "
                           f"Bits wrong: {err['bits_wrong']}\n")

        f.write("\n" + "="*70 + "\n")
        f.write("End of Report\n")
        f.write("="*70 + "\n")

    print(f"Text report saved:  {txt_filename}")

    return json_filename, txt_filename

def main():
    # Configuration
    DATA_LENGTH = 1000

    # Prompt for COM port
    print("\nRS485 Adapter Data Integrity Test")
    print("-" * 40)
    port = input("Enter COM port (e.g., COM3): ").strip()

    # Pattern selection
    print_pattern_menu()

    run_all_patterns = False
    run_all_bauds = False
    pattern_type = None

    while True:
        try:
            choice = int(input("\nSelect pattern (1-10): "))
            if choice == 10:
                run_all_patterns = True
                run_all_bauds = True
                break
            elif choice == 9:
                run_all_patterns = True
                break
            elif 1 <= choice <= 8:
                pattern_type = DataPattern(choice)
                break
            else:
                print("Invalid choice. Please select 1-10.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # If running all baud rates, ask for confirmation
    if run_all_bauds:
        print("\n" + "="*60)
        print("COMPREHENSIVE TEST MODE")
        print("="*60)
        print(f"Will test {len(DataPattern)} patterns at {len(BAUD_RATES)} baud rates")
        print(f"Total tests: {len(DataPattern) * len(BAUD_RATES)}")
        print(f"Baud rates: {', '.join(map(str, BAUD_RATES))}")
        print(f"Estimated time: ~{len(DataPattern) * len(BAUD_RATES) * 4} seconds")
        print("="*60)
        confirm = input("\nProceed? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Test cancelled.")
            return

    all_test_results = []

    # Open serial port at initial 9600 baud
    print(f"\nOpening {port} at 9600 bps (initial baud rate)...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=5
        )
        time.sleep(2)  # Wait for port to stabilize
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print("✓ Port opened successfully")

    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port: {e}")
        sys.exit(1)

    # Determine which baud rates to test
    baud_rates_to_test = BAUD_RATES if run_all_bauds else [9600]
    current_baud = 9600

    for baud_rate in baud_rates_to_test:
        print("\n\n" + "="*70)
        print(f"TESTING AT {baud_rate} BAUD")
        print("="*70)

        # Negotiate baud rate change if needed
        if baud_rate != current_baud:
            # Wait a bit after previous test before sending command
            time.sleep(1.0)

            # Clear any pending data
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            new_ser = negotiate_baud_rate(ser, baud_rate)
            if new_ser is None:
                print(f"✗ Failed to change to {baud_rate} baud, skipping...")
                # Try to continue with remaining tests at current baud
                continue
            ser = new_ser
            current_baud = baud_rate
        else:
            print(f"Already at {baud_rate} baud")

        test_results = []

        if run_all_patterns:
            # Run all patterns at this baud rate
            print(f"\nRunning all {len(DataPattern)} patterns at {baud_rate} bps...")

            seed = 12345
            for pattern in DataPattern:
                print(f"\n{'='*60}")
                print(f"Pattern {pattern.value}/{len(DataPattern)}: {pattern.name} @ {baud_rate} bps")
                print(f"{'='*60}")

                result = run_single_test(ser, pattern, DATA_LENGTH, baud_rate, seed)
                test_results.append(result)
                all_test_results.append(result)

                # Small delay between tests
                time.sleep(0.5)

            # Print summary for this baud rate
            print("\n" + "="*60)
            print(f"SUMMARY FOR {baud_rate} BAUD")
            print("="*60)
            print(f"Tests Run:            {len(test_results)}")
            print(f"Tests Passed:         {sum(1 for r in test_results if r['bit_errors'] == 0)}")
            print(f"Tests Failed:         {sum(1 for r in test_results if r['bit_errors'] > 0)}")
            print(f"Total Bit Errors:     {sum(r['bit_errors'] for r in test_results)}")
            print("="*60)

        else:
            # Run single pattern at this baud rate
            seed = 12345
            if pattern_type in [DataPattern.RANDOM, DataPattern.PRBS]:
                seed_input = input(f"Enter seed (default: {seed}): ").strip()
                if seed_input:
                    try:
                        seed = int(seed_input)
                    except ValueError:
                        print(f"Invalid seed, using default: {seed}")

            result = run_single_test(ser, pattern_type, DATA_LENGTH, baud_rate, seed)
            test_results.append(result)
            all_test_results.append(result)

        # Don't close port between baud rates when testing multiple rates
        if not run_all_bauds:
            ser.close()
            print(f"\nClosed port.")

    # Final summary if testing multiple baud rates
    if run_all_bauds:
        print("\n\n" + "="*70)
        print("FINAL SUMMARY - ALL BAUD RATES")
        print("="*70)
        print(f"Total Tests Run:      {len(all_test_results)}")
        print(f"Tests Passed:         {sum(1 for r in all_test_results if r['bit_errors'] == 0)}")
        print(f"Tests Failed:         {sum(1 for r in all_test_results if r['bit_errors'] > 0)}")
        print(f"Total Bytes Tested:   {sum(r['bytes_sent'] for r in all_test_results)}")
        print(f"Total Bit Errors:     {sum(r['bit_errors'] for r in all_test_results)}")
        print("="*70)

        # Show results by baud rate
        print("\nResults by Baud Rate:")
        for baud_rate in baud_rates_to_test:
            baud_results = [r for r in all_test_results if r['baud_rate'] == baud_rate]
            passed = sum(1 for r in baud_results if r['bit_errors'] == 0)
            failed = sum(1 for r in baud_results if r['bit_errors'] > 0)
            print(f"  {baud_rate:>6} bps: {passed}/{len(baud_results)} passed, {failed} failed")

    # Close serial port
    if ser and ser.is_open:
        ser.close()
        print("\nSerial port closed.")

    # Save results
    if len(all_test_results) > 0:
        if run_all_bauds or run_all_patterns:
            save_results(all_test_results, port, all_test_results[0]['baud_rate'] if len(all_test_results) == 1 else 'multi')
        else:
            save_choice = input("\nSave results to file? (y/n): ").strip().lower()
            if save_choice == 'y':
                save_results(all_test_results, port, all_test_results[0]['baud_rate'])

    print("\nTest completed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
