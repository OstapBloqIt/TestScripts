#!/usr/bin/env python3
"""
RS485 Simple Listener - Linux/iMX8M Mini Version
Direct Python equivalent of esp32_rs485_simple_listener.ino

Listens for messages on RS485 and responds with ACK
Handles baud rate change commands

Hardware Setup:
- Toradex Verdin iMX8M Mini with native UART
- Default port: /dev/ttymxc0 (native UART)
- A+/B- differential signals to PC via RS485

This is the Linux equivalent of the ESP32 simple listener
"""

import serial
import time
import sys
import argparse
from datetime import datetime

# Configuration
DEFAULT_PORT = '/dev/ttymxc0'  # Native UART on iMX8M Mini
BAUD_RATE = 9600  # Starting baud rate
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]

# Status
message_count = 0
last_activity_time = 0


def setup_serial(port, baudrate):
    """Initialize serial port for RS485 communication"""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            write_timeout=1.0
        )

        # Allow port to stabilize
        time.sleep(0.1)

        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return None


def print_startup_banner(port, baudrate):
    """Print startup information"""
    print("\n" + "="*43)
    print("RS485 Simple Listener")
    print(f"Linux/iMX8M Mini @ {baudrate} baud")
    print("="*43)
    print(f"Listening on RS485 at {baudrate} bps")
    print(f"Port: {port}")
    print("Waiting for messages...\n")


def print_status(uptime_seconds):
    """Print periodic status update"""
    print("\n--- Status ---")
    print(f"Messages received: {message_count}")
    print(f"Last activity: {int(time.time() - last_activity_time)} seconds ago")
    print(f"Uptime: {uptime_seconds} seconds")
    print("-------------\n")


def main():
    global message_count, last_activity_time

    parser = argparse.ArgumentParser(
        description='RS485 Simple Listener - Linux Version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Listen on native UART (default)
  python3 rs485_listener_linux.py

  # Specify different UART
  python3 rs485_listener_linux.py /dev/ttymxc1

Setup Instructions:
  1. Connect RS485 transceiver to iMX8M Mini native UART (/dev/ttymxc0)
  2. Run this script: python3 rs485_listener_linux.py
  3. Run sender on PC: python3 pc_baud_rate_sweep.py COM3

This is the direct Python equivalent of esp32_rs485_simple_listener.ino
        '''
    )

    parser.add_argument('port', nargs='?', default=DEFAULT_PORT,
                       help=f'Serial port (default: {DEFAULT_PORT})')
    parser.add_argument('--baud', type=int, default=BAUD_RATE,
                       choices=BAUD_RATES,
                       help=f'Initial baud rate (default: {BAUD_RATE})')

    args = parser.parse_args()

    # Check if port exists
    import os
    if not os.path.exists(args.port):
        print(f"Error: Port {args.port} does not exist!")
        print("\nAvailable native UART ports:")
        for dev in ['/dev/ttymxc0', '/dev/ttymxc1', '/dev/ttymxc2']:
            if os.path.exists(dev):
                print(f"  {dev}")
        sys.exit(1)

    # Initialize serial port
    current_baud = args.baud
    ser = setup_serial(args.port, current_baud)

    if ser is None:
        sys.exit(1)

    print_startup_banner(args.port, current_baud)

    # Startup LED equivalent (just print message)
    print("Starting up...")
    time.sleep(0.6)
    print("Ready!\n")

    start_time = time.time()
    last_activity_time = time.time()
    last_heartbeat = time.time()
    last_status = time.time()

    incoming_message = ""

    try:
        while True:
            # Heartbeat equivalent (print dot every second to show we're alive)
            if time.time() - last_heartbeat > 1.0:
                sys.stdout.write('.')
                sys.stdout.flush()
                last_heartbeat = time.time()

            # Check for incoming data
            if ser.in_waiting > 0:
                incoming_char = ser.read(1).decode('utf-8', errors='ignore')

                last_activity_time = time.time()

                # Print raw byte value for debugging (like the Arduino sketch)
                sys.stdout.write(f"0x{ord(incoming_char):02x} ")
                sys.stdout.flush()

                # Check for end of message
                if incoming_char == '\n' or incoming_char == '\r':
                    if len(incoming_message) > 0:
                        # Message complete
                        message_count += 1

                        print()  # New line
                        print(f"[MSG #{message_count}] {incoming_message}")
                        print()

                        # Check if it's a baud change command
                        if incoming_message.startswith("CHANGE_BAUD_"):
                            try:
                                # Parse: "CHANGE_BAUD_115200"
                                new_baud = int(incoming_message.split('_')[2])

                                if new_baud in BAUD_RATES:
                                    print(f"*** BAUD CHANGE REQUEST: {current_baud} -> {new_baud} ***")

                                    # Send ACK at current baud rate
                                    ack_msg = "ACK_BAUD_CHANGE\n"
                                    ser.write(ack_msg.encode('utf-8'))
                                    ser.flush()
                                    print(f"Sent ACK at {current_baud} baud")

                                    # Wait for ACK to be transmitted
                                    time.sleep(0.2)

                                    # Switch to new baud rate
                                    ser.close()
                                    current_baud = new_baud
                                    ser = setup_serial(args.port, current_baud)

                                    if ser:
                                        print(f"Switched to {current_baud} baud\n")
                                    else:
                                        print(f"ERROR: Failed to switch to {current_baud} baud")
                                        sys.exit(1)
                                else:
                                    print(f"ERROR: Invalid baud rate {new_baud}")
                            except (IndexError, ValueError) as e:
                                print(f"ERROR: Invalid baud change command: {incoming_message}")
                        else:
                            # Regular test packet - send ACK response
                            response = f"ACK_{incoming_message}\n"
                            ser.write(response.encode('utf-8'))
                            ser.flush()
                            print("Sent ACK")

                        # Flash LED equivalent (just a short delay)
                        time.sleep(0.05)

                        # Clear message buffer
                        incoming_message = ""

                elif ord(incoming_char) >= 32 and ord(incoming_char) <= 126:
                    # Printable ASCII character
                    incoming_message += incoming_char
                else:
                    # Non-printable character - just shown in hex output above
                    pass

            # Print periodic status (every 30 seconds)
            if time.time() - last_status > 30.0:
                uptime = int(time.time() - start_time)
                print_status(uptime)
                last_status = time.time()

            # Small delay to prevent CPU spinning
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nStopped listener")
        print(f"Total messages received: {message_count}")
        uptime = int(time.time() - start_time)
        print(f"Uptime: {uptime} seconds")

    finally:
        if ser and ser.is_open:
            ser.close()
            print(f"Closed {args.port}")


if __name__ == '__main__':
    main()
