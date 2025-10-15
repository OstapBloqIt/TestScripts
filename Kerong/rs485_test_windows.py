#!/usr/bin/env python3
"""
RS485 Communication Test - Windows Side (Sender/Controller)
Tests RS485 communication at multiple baud rates by sending commands to receiver
Requires: pip install pyserial
"""

import serial
import serial.tools.list_ports
import time
import sys
import argparse
import json
import hashlib
from datetime import datetime

# Test configurations
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]
TEST_MESSAGE = "RS485_TEST_PACKET"
RESPONSE_TIMEOUT = 2.0
PACKETS_PER_TEST = 10
BAUD_CHANGE_CMD = "CHANGE_BAUD"
BAUD_CHANGE_ACK = "ACK_BAUD_CHANGE"


class RS485TesterWindows:
    def __init__(self, port):
        """
        Initialize RS485 tester for Windows (Sender Mode)

        Args:
            port: Serial port (e.g., COM3)
        """
        self.port = port
        self.ser = None
        self.test_results = []

    def configure_serial(self, baudrate):
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
                timeout=RESPONSE_TIMEOUT,
                write_timeout=1.0
            )

            # Set RTS/DTR low (not driving)
            self.ser.rts = False
            self.ser.dtr = False

            time.sleep(0.1)  # Allow port to stabilize

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Configured {self.port} at {baudrate} baud")
            return True

        except serial.SerialException as e:
            print(f"Error configuring port: {e}")
            return False

    def send_baud_change_command(self, new_baudrate):
        """Send baud rate change command and wait for ACK"""
        cmd = f"{BAUD_CHANGE_CMD}_{new_baudrate}\n"

        try:
            print(f"  Sending baud change command: {cmd.strip()}")

            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Send command
            self.ser.write(cmd.encode('utf-8'))
            self.ser.flush()

            # Wait for acknowledgment
            time.sleep(0.2)
            response = self.ser.readline().decode('utf-8', errors='ignore').strip()

            if response == BAUD_CHANGE_ACK:
                print(f"  ✓ Received ACK: {response}")
                return True
            else:
                print(f"  ✗ Unexpected response: '{response}'")
                return False

        except Exception as e:
            print(f"  ✗ Error sending baud change command: {e}")
            return False

    def generate_test_message(self, baudrate, sequence_num):
        """Generate a test message with sequence number and checksum"""
        base_msg = f"{TEST_MESSAGE}_{baudrate}_{sequence_num:03d}"
        checksum = hashlib.md5(base_msg.encode()).hexdigest()[:8]
        return f"{base_msg}_{checksum}\n"

    def validate_response(self, sent_msg, received_msg):
        """Validate if response matches expected format"""
        expected_response = f"ACK_{sent_msg.strip()}"
        return received_msg.strip() == expected_response

    def run_test_at_baudrate(self, baudrate, is_first=False):
        """Run test at specific baud rate"""
        print(f"\n{'='*60}")
        print(f"Testing Baud Rate: {baudrate}")
        print(f"{'='*60}")

        result = {
            'baudrate': baudrate,
            'timestamp': datetime.now().isoformat(),
            'total_messages': PACKETS_PER_TEST,
            'successful_messages': 0,
            'failed_messages': 0,
            'timeout_errors': 0,
            'success_rate': 0.0,
            'average_response_time': 0.0,
            'errors': []
        }

        try:
            # Configure serial port at this baud rate
            if not self.configure_serial(baudrate):
                result['errors'].append("Failed to configure serial port")
                return result

            # Send baud change command if not first test
            if not is_first:
                if not self.send_baud_change_command(baudrate):
                    print(f"  ERROR: Baud change command failed!")
                    print(f"  Cannot continue - sender and receiver are out of sync")
                    result['errors'].append("Baud change negotiation failed")
                    return result

                # Wait for receiver to switch baud rate
                time.sleep(0.5)

                # Reconfigure our port to new baud rate
                self.ser.baudrate = baudrate
                time.sleep(0.3)
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()

            response_times = []

            print(f"\nSending {PACKETS_PER_TEST} test packets...")

            for i in range(PACKETS_PER_TEST):
                progress = (i + 1) / PACKETS_PER_TEST * 100
                print(f"\rProgress: {progress:5.1f}% ({i+1}/{PACKETS_PER_TEST})", end='', flush=True)

                try:
                    # Clear input buffer
                    self.ser.reset_input_buffer()

                    # Generate test message
                    test_msg = self.generate_test_message(baudrate, i + 1)

                    # Send packet and measure time
                    start_time = time.time()
                    self.ser.write(test_msg.encode('utf-8'))
                    self.ser.flush()

                    # Wait for echo/response
                    response = self.ser.readline().decode('utf-8', errors='ignore')
                    end_time = time.time()

                    if response:
                        response_time = (end_time - start_time) * 1000  # Convert to ms
                        response_times.append(response_time)

                        if self.validate_response(test_msg, response):
                            result['successful_messages'] += 1
                        else:
                            result['failed_messages'] += 1
                            result['errors'].append(f"Packet {i+1}: Invalid response")
                    else:
                        result['timeout_errors'] += 1
                        result['failed_messages'] += 1
                        result['errors'].append(f"Packet {i+1}: Timeout")

                    # Small delay between packets
                    time.sleep(0.05)

                except Exception as e:
                    result['failed_messages'] += 1
                    result['errors'].append(f"Packet {i+1}: {str(e)}")

            print()  # New line after progress

            # Calculate statistics
            result['success_rate'] = (result['successful_messages'] / result['total_messages']) * 100

            if response_times:
                result['average_response_time'] = sum(response_times) / len(response_times)

            print(f"\nResults:")
            print(f"  Success: {result['successful_messages']}/{result['total_messages']} ({result['success_rate']:.1f}%)")
            print(f"  Failed:  {result['failed_messages']}/{result['total_messages']}")
            print(f"  Timeouts: {result['timeout_errors']}")
            if response_times:
                print(f"  Avg RTT: {result['average_response_time']:.2f} ms")

        except Exception as e:
            result['errors'].append(f"Serial error: {str(e)}")
            print(f"\nError during test: {e}")

        return result

    def run_full_test_suite(self):
        """Run tests at all configured baud rates"""
        print(f"\n{'='*60}")
        print(f"RS485 Communication Test Suite - Windows (Sender Mode)")
        print(f"{'='*60}")
        print(f"Port: {self.port}")
        print(f"Starting baud rate: {BAUD_RATES[0]}")
        print(f"Baud rates to test: {', '.join(map(str, BAUD_RATES))}")
        print(f"Packets per test: {PACKETS_PER_TEST}")
        print(f"{'='*60}\n")

        start_time = datetime.now()

        for idx, baudrate in enumerate(BAUD_RATES):
            overall_progress = (idx / len(BAUD_RATES)) * 100
            print(f"\n\nOverall Progress: {overall_progress:.1f}% ({idx+1}/{len(BAUD_RATES)} baud rates)")

            result = self.run_test_at_baudrate(baudrate, is_first=(idx == 0))
            self.test_results.append(result)

            # Check if baud change failed - if so, stop the entire test suite
            if "Baud change negotiation failed" in result['errors']:
                print("\n\n*** TEST SUITE ABORTED ***")
                print("Baud rate change failed - sender and receiver are out of sync")
                print("Cannot continue with remaining tests")
                break

            time.sleep(0.5)

        end_time = datetime.now()

        # Print summary
        self.print_summary()

        # Save results
        self.save_results(start_time, end_time)

    def print_summary(self):
        """Print test summary table"""
        print(f"\n\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        print(f"{'Baud Rate':<12} {'Success':<10} {'Failed':<10} {'Rate':<10} {'Avg RTT':<10}")
        print(f"{'-'*60}")

        for result in self.test_results:
            avg_rtt = f"{result['average_response_time']:.2f} ms" if result['average_response_time'] > 0 else "N/A"
            print(f"{result['baudrate']:<12} "
                  f"{result['successful_messages']:<10} "
                  f"{result['failed_messages']:<10} "
                  f"{result['success_rate']:.1f}%{'':<6} "
                  f"{avg_rtt}")

        print(f"{'='*60}")

        # Overall statistics
        total_packets = len(self.test_results) * PACKETS_PER_TEST
        total_success = sum(r['successful_messages'] for r in self.test_results)
        overall_rate = (total_success / total_packets * 100) if total_packets > 0 else 0

        print(f"\nOverall Success Rate: {total_success}/{total_packets} ({overall_rate:.1f}%)")

        # Best performing baud rate
        if self.test_results:
            best = max(self.test_results, key=lambda x: (x['success_rate'], -x['average_response_time']))
            avg_rtt = f"{best['average_response_time']:.2f} ms" if best['average_response_time'] > 0 else "N/A"
            print(f"Best Performing: {best['baudrate']} baud "
                  f"({best['success_rate']:.1f}% success, {avg_rtt} RTT)")

    def save_results(self, start_time, end_time):
        """Save test results to JSON file"""
        duration = end_time - start_time

        report = {
            'test_info': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'port': self.port,
                'timeout': RESPONSE_TIMEOUT,
                'messages_per_baud_rate': PACKETS_PER_TEST,
                'baud_rates_tested': BAUD_RATES
            },
            'results': self.test_results
        }

        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        json_filename = f"rs485_test_windows_{timestamp}.json"

        with open(json_filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nResults saved to: {json_filename}")

    def close(self):
        """Close serial port"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"\nClosed {self.port}")


def list_serial_ports():
    """List all available serial ports"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found!")
        return []

    print("\nAvailable Serial Ports:")
    print(f"{'Port':<10} {'Description':<40} {'HWID':<30}")
    print("-" * 80)
    for port in ports:
        print(f"{port.device:<10} {port.description:<40} {port.hwid:<30}")
    print()
    return [port.device for port in ports]


def main():
    parser = argparse.ArgumentParser(
        description='RS485 Communication Test - Windows Side (Sender)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List available COM ports
  python rs485_test_windows.py --list

  # Run baud rate sweep test
  python rs485_test_windows.py COM3

Setup Instructions:
  1. Install Python 3.7 or later
  2. Install pyserial: pip install pyserial
  3. Connect RS485-to-USB adapter to your Windows PC
  4. Check COM port number in Device Manager or use --list
  5. On Linux side, run: python3 rs485_test_linux.py /dev/ttymxc0
  6. On Windows side, run: python rs485_test_windows.py COM3
        '''
    )

    parser.add_argument('port', nargs='?', help='Serial port (e.g., COM3)')
    parser.add_argument('--list', action='store_true',
                       help='List available serial ports and exit')

    args = parser.parse_args()

    # List ports if requested
    if args.list:
        list_serial_ports()
        sys.exit(0)

    # Port is required if not listing
    if not args.port:
        print("Error: Serial port is required!")
        print("\nUse --list to see available ports:")
        list_serial_ports()
        parser.print_help()
        sys.exit(1)

    # Validate port exists
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    if args.port not in available_ports:
        print(f"Error: Port {args.port} not found!")
        list_serial_ports()
        sys.exit(1)

    tester = RS485TesterWindows(args.port)

    try:
        tester.run_full_test_suite()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.close()


if __name__ == '__main__':
    main()
