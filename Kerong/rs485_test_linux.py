#!/usr/bin/env python3
"""
RS485 Communication Test - Linux Side (Listener/Responder)
Listens for commands and test packets, responds with ACKs
Similar to ESP32 simple listener pattern
"""

import serial
import time
import sys
import argparse
from datetime import datetime

# Test configurations
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]
BAUD_CHANGE_CMD = "CHANGE_BAUD"
BAUD_CHANGE_ACK = "ACK_BAUD_CHANGE"
CURRENT_BAUD = 9600  # Always start at 9600


class RS485Listener:
    def __init__(self, port):
        """
        Initialize RS485 listener

        Args:
            port: Serial port device (e.g., /dev/ttymxc0)
        """
        self.port = port
        self.ser = None
        self.current_baud = CURRENT_BAUD
        self.message_count = 0

    def configure_rs485(self, baudrate):
        """Configure serial port for RS485 communication"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(
                port=self.port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
                write_timeout=1.0
            )

            # Allow port to stabilize
            time.sleep(0.1)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Configured {self.port} at {baudrate} baud")
            return True

        except serial.SerialException as e:
            print(f"Error configuring port: {e}")
            return False

    def run_listener(self):
        """Run as listener - receives commands and echoes test packets"""
        print(f"\n{'='*60}")
        print(f"RS485 Listener Mode")
        print(f"{'='*60}")
        print(f"Port: {self.port}")
        print(f"Starting baud rate: {self.current_baud}")
        print(f"Supported baud rates: {', '.join(map(str, BAUD_RATES))}")
        print(f"{'='*60}\n")

        if not self.configure_rs485(self.current_baud):
            return

        print(f"Listening for data on {self.port}...")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                # Check for incoming data
                if self.ser.in_waiting > 0:
                    # Read until newline
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                    if not line:
                        continue

                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    self.message_count += 1

                    # Check if it's a baud change command
                    if line.startswith(BAUD_CHANGE_CMD):
                        self.handle_baud_change_command(line, timestamp)
                    else:
                        # Regular test packet - echo it back with ACK prefix
                        self.handle_test_packet(line, timestamp)

                # Small delay to prevent CPU spinning
                time.sleep(0.01)

        except KeyboardInterrupt:
            print(f"\n\nStopped listener. Total messages: {self.message_count}")

    def handle_baud_change_command(self, command, timestamp):
        """Handle baud rate change command"""
        try:
            # Parse command: "CHANGE_BAUD_115200"
            parts = command.split('_')
            if len(parts) >= 3:
                new_baud = int(parts[2])

                if new_baud in BAUD_RATES:
                    print(f"\n[{timestamp}] *** BAUD CHANGE REQUEST: {self.current_baud} -> {new_baud} ***")

                    # Send ACK at current baud rate
                    ack_msg = f"{BAUD_CHANGE_ACK}\n"
                    self.ser.write(ack_msg.encode('utf-8'))
                    self.ser.flush()
                    print(f"[{timestamp}] Sent ACK at {self.current_baud} baud")

                    # Wait for ACK to be transmitted
                    time.sleep(0.2)

                    # Switch to new baud rate
                    self.current_baud = new_baud
                    if self.configure_rs485(self.current_baud):
                        print(f"[{timestamp}] Switched to {self.current_baud} baud\n")
                    else:
                        print(f"[{timestamp}] ERROR: Failed to switch to {self.current_baud} baud\n")
                else:
                    print(f"[{timestamp}] ERROR: Invalid baud rate {new_baud}")
            else:
                print(f"[{timestamp}] ERROR: Invalid command format: {command}")

        except (IndexError, ValueError) as e:
            print(f"[{timestamp}] ERROR: Failed to parse baud change command: {command}")

    def handle_test_packet(self, packet, timestamp):
        """Handle test packet - echo it back with ACK prefix"""
        print(f"[{timestamp}] Received #{self.message_count}: {packet}")

        # Send ACK response
        response = f"ACK_{packet}\n"
        self.ser.write(response.encode('utf-8'))
        self.ser.flush()

        print(f"[{timestamp}] Sent ACK")

    def close(self):
        """Close serial port"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"\nClosed {self.port}")


def main():
    parser = argparse.ArgumentParser(
        description='RS485 Communication Test - Linux Side (Listener)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run as listener (default)
  python3 rs485_test_linux.py /dev/ttymxc0

Setup Instructions:
  1. Connect RS485 adapter to Linux device
  2. Run this script on Linux side: python3 rs485_test_linux.py /dev/ttymxc0
  3. Run sender on Windows side: python rs485_test_windows.py COM3

How It Works:
  - Starts listening at 9600 baud
  - Receives CHANGE_BAUD_<rate> commands from sender
  - Acknowledges and switches to new baud rate
  - Echoes test packets back with "ACK_" prefix
        '''
    )

    parser.add_argument('port', help='Serial port device (e.g., /dev/ttymxc0)')

    args = parser.parse_args()

    # Check if port exists
    import os
    if not os.path.exists(args.port):
        print(f"Error: Port {args.port} does not exist!")
        print("\nAvailable serial ports:")
        for dev in ['/dev/ttymxc0', '/dev/ttymxc1', '/dev/ttymxc2', '/dev/ttyUSB0']:
            if os.path.exists(dev):
                print(f"  {dev}")
        sys.exit(1)

    listener = RS485Listener(args.port)

    try:
        listener.run_listener()

    except KeyboardInterrupt:
        print("\n\nListener interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        listener.close()


if __name__ == '__main__':
    main()
