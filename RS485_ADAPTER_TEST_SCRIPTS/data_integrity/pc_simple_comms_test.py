#!/usr/bin/env python3
"""
Simple RS485 Communication Test - PC Side
Sends messages to ESP32 and displays the ACK response
"""

import serial
import time
import sys

def main():
    # Configuration
    BAUD_RATE = 9600
    TIMEOUT = 5  # seconds

    print("\n" + "="*60)
    print("Simple RS485 Communication Test")
    print("="*60)

    # Get COM port
    port = input("Enter COM port (e.g., COM3): ").strip()

    # Open serial port
    try:
        ser = serial.Serial(
            port=port,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT
        )
        print(f"\nOpened {port} at {BAUD_RATE} bps")
        time.sleep(2)  # Wait for port to stabilize
        ser.reset_input_buffer()
        ser.reset_output_buffer()

    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("Type messages to send (or 'quit' to exit)")
    print("="*60 + "\n")

    try:
        while True:
            # Get message from user
            message = input("Enter message: ").strip()

            if message.lower() == 'quit':
                print("Exiting...")
                break

            if not message:
                continue

            # Send message (with newline as terminator)
            print("\n" + "-"*60)
            print(f"SENDING: {message}")
            ser.write((message + "\n").encode('utf-8'))
            ser.flush()

            # Wait for response
            print("Waiting for ACK response...")
            response = ""
            start_time = time.time()

            while True:
                if ser.in_waiting > 0:
                    char = ser.read(1).decode('utf-8', errors='ignore')
                    response += char

                    # Check for newline (end of response)
                    if char == '\n':
                        break

                # Check timeout
                if time.time() - start_time > TIMEOUT:
                    print("TIMEOUT: No response received")
                    break

                time.sleep(0.01)

            if response:
                response = response.strip()
                print(f"RECEIVED: {response}")

                # Verify ACK
                expected_ack = f"ACK: {message}"
                if response == expected_ack:
                    print("✓ ACK verified successfully!")
                else:
                    print(f"✗ ACK mismatch! Expected: '{expected_ack}'")
            else:
                print("✗ No response received")

            print("-"*60 + "\n")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    finally:
        ser.close()
        print("Serial port closed.")

if __name__ == "__main__":
    main()
