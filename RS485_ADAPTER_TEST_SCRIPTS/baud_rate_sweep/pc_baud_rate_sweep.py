#!/usr/bin/env python3
"""
RS485 Adapter Baud Rate Sweep Test - PC Side
Sends test messages at different baud rates and measures BER
"""

import serial
import time
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple
import argparse
import sys

class BaudRateSweepTest:
    def __init__(self, port: str, timeout: float = 2.0):
        self.port = port
        self.timeout = timeout
        self.test_results = []
        self.baud_rates = [9600, 19200, 38400, 57600, 115200]
        self.test_message = "RS485_TEST_MESSAGE_"
        self.message_count = 100

    def generate_test_message(self, sequence_num: int) -> str:
        """Generate a test message with sequence number and checksum"""
        base_msg = f"{self.test_message}{sequence_num:04d}"
        checksum = hashlib.md5(base_msg.encode()).hexdigest()[:8]
        return f"{base_msg}_{checksum}\n"

    def validate_response(self, sent_msg: str, received_msg: str) -> bool:
        """Validate if response matches expected format"""
        expected_response = f"ACK_{sent_msg.strip()}\n"
        return received_msg.strip() == expected_response.strip()

    def calculate_ber(self, sent_bits: str, received_bits: str) -> float:
        """Calculate Bit Error Rate between sent and received data"""
        if len(sent_bits) != len(received_bits):
            return 1.0  # 100% error if lengths don't match

        errors = sum(s != r for s, r in zip(sent_bits, received_bits))
        return errors / len(sent_bits) if len(sent_bits) > 0 else 1.0

    def test_baud_rate(self, baud_rate: int) -> Dict:
        """Test communication at a specific baud rate"""
        print(f"\n{'='*50}")
        print(f"Testing baud rate: {baud_rate} bps")
        print(f"{'='*50}")

        result = {
            'baud_rate': baud_rate,
            'timestamp': datetime.now().isoformat(),
            'total_messages': self.message_count,
            'successful_messages': 0,
            'failed_messages': 0,
            'timeout_errors': 0,
            'bit_errors': 0,
            'total_bits': 0,
            'ber': 0.0,
            'success_rate': 0.0,
            'average_response_time': 0.0,
            'errors': []
        }

        try:
            # Open serial connection
            ser = serial.Serial(
                port=self.port,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )

            # Wait for connection to stabilize
            time.sleep(0.5)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            response_times = []

            for i in range(self.message_count):
                progress = (i + 1) / self.message_count * 100
                print(f"\rProgress: {progress:5.1f}% ({i+1}/{self.message_count})", end='', flush=True)

                test_msg = self.generate_test_message(i)

                try:
                    start_time = time.time()

                    # Send message
                    ser.write(test_msg.encode())

                    # Wait for response
                    response = ser.readline().decode('utf-8', errors='ignore')

                    end_time = time.time()
                    response_time = end_time - start_time

                    if response:
                        response_times.append(response_time)

                        if self.validate_response(test_msg, response):
                            result['successful_messages'] += 1
                        else:
                            result['failed_messages'] += 1
                            result['errors'].append(f"Msg {i}: Invalid response format")

                            # Calculate bit errors
                            expected_response = f"ACK_{test_msg.strip()}"
                            sent_bits = ''.join(format(ord(c), '08b') for c in expected_response)
                            received_bits = ''.join(format(ord(c), '08b') for c in response.strip())

                            # Pad shorter string with zeros
                            max_len = max(len(sent_bits), len(received_bits))
                            sent_bits = sent_bits.ljust(max_len, '0')
                            received_bits = received_bits.ljust(max_len, '0')

                            bit_errors = sum(s != r for s, r in zip(sent_bits, received_bits))
                            result['bit_errors'] += bit_errors
                            result['total_bits'] += max_len
                    else:
                        result['timeout_errors'] += 1
                        result['failed_messages'] += 1
                        result['errors'].append(f"Msg {i}: Timeout")

                except Exception as e:
                    result['failed_messages'] += 1
                    result['errors'].append(f"Msg {i}: Exception - {str(e)}")

                # Small delay between messages
                time.sleep(0.01)

            ser.close()

        except Exception as e:
            result['errors'].append(f"Serial connection error: {str(e)}")
            print(f"\nError opening serial port: {e}")
            return result

        # Calculate statistics
        if result['total_bits'] > 0:
            result['ber'] = result['bit_errors'] / result['total_bits']

        result['success_rate'] = (result['successful_messages'] / result['total_messages']) * 100

        if response_times:
            result['average_response_time'] = sum(response_times) / len(response_times)

        print(f"\nCompleted: {result['successful_messages']}/{result['total_messages']} messages successful")
        print(f"Success Rate: {result['success_rate']:.1f}%")
        print(f"BER: {result['ber']:.2e}")

        return result

    def run_sweep(self) -> List[Dict]:
        """Run the complete baud rate sweep test"""
        print(f"Starting RS485 Adapter Baud Rate Sweep Test")
        print(f"Port: {self.port}")
        print(f"Baud rates: {self.baud_rates}")
        print(f"Messages per rate: {self.message_count}")
        print(f"Timeout: {self.timeout}s")

        start_time = datetime.now()

        for i, baud_rate in enumerate(self.baud_rates):
            overall_progress = (i / len(self.baud_rates)) * 100
            print(f"\n\nOverall Progress: {overall_progress:.1f}% ({i+1}/{len(self.baud_rates)} baud rates)")

            result = self.test_baud_rate(baud_rate)
            self.test_results.append(result)

            # Wait between baud rate changes
            if i < len(self.baud_rates) - 1:
                print("\nWaiting 2 seconds before next baud rate...")
                time.sleep(2)

        end_time = datetime.now()

        # Generate final report
        self.generate_report(start_time, end_time)

        return self.test_results

    def generate_report(self, start_time: datetime, end_time: datetime):
        """Generate and save the test execution report"""
        duration = end_time - start_time

        report = {
            'test_info': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'port': self.port,
                'timeout': self.timeout,
                'messages_per_baud_rate': self.message_count,
                'baud_rates_tested': self.baud_rates
            },
            'summary': {
                'total_baud_rates': len(self.baud_rates),
                'total_messages_sent': len(self.baud_rates) * self.message_count,
                'overall_success_rate': 0.0,
                'best_baud_rate': {'rate': 0, 'success_rate': 0.0, 'ber': 1.0},
                'worst_baud_rate': {'rate': 0, 'success_rate': 100.0, 'ber': 0.0}
            },
            'detailed_results': self.test_results
        }

        # Calculate summary statistics
        total_successful = sum(r['successful_messages'] for r in self.test_results)
        total_messages = sum(r['total_messages'] for r in self.test_results)

        if total_messages > 0:
            report['summary']['overall_success_rate'] = (total_successful / total_messages) * 100

        # Find best and worst performing baud rates
        for result in self.test_results:
            success_rate = result['success_rate']
            ber = result['ber']

            # Best = highest success rate, lowest BER
            if (success_rate > report['summary']['best_baud_rate']['success_rate'] or
                (success_rate == report['summary']['best_baud_rate']['success_rate'] and
                 ber < report['summary']['best_baud_rate']['ber'])):
                report['summary']['best_baud_rate'] = {
                    'rate': result['baud_rate'],
                    'success_rate': success_rate,
                    'ber': ber
                }

            # Worst = lowest success rate, highest BER
            if (success_rate < report['summary']['worst_baud_rate']['success_rate'] or
                (success_rate == report['summary']['worst_baud_rate']['success_rate'] and
                 ber > report['summary']['worst_baud_rate']['ber'])):
                report['summary']['worst_baud_rate'] = {
                    'rate': result['baud_rate'],
                    'success_rate': success_rate,
                    'ber': ber
                }

        # Save JSON report
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        json_filename = f"rs485_baud_sweep_report_{timestamp}.json"

        with open(json_filename, 'w') as f:
            json.dump(report, f, indent=2)

        # Generate human-readable report
        text_filename = f"rs485_baud_sweep_report_{timestamp}.txt"

        with open(text_filename, 'w') as f:
            f.write("RS485 ADAPTER BAUD RATE SWEEP TEST REPORT\n")
            f.write("=" * 50 + "\n\n")

            f.write(f"Test Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Test End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Duration: {duration.total_seconds():.1f} seconds\n")
            f.write(f"Serial Port: {self.port}\n")
            f.write(f"Timeout: {self.timeout}s\n\n")

            f.write("SUMMARY\n")
            f.write("-" * 20 + "\n")
            f.write(f"Baud Rates Tested: {', '.join(map(str, self.baud_rates))}\n")
            f.write(f"Messages per Baud Rate: {self.message_count}\n")
            f.write(f"Total Messages Sent: {total_messages}\n")
            f.write(f"Overall Success Rate: {report['summary']['overall_success_rate']:.1f}%\n\n")

            best = report['summary']['best_baud_rate']
            worst = report['summary']['worst_baud_rate']
            f.write(f"Best Performing Baud Rate: {best['rate']} bps ({best['success_rate']:.1f}% success, BER: {best['ber']:.2e})\n")
            f.write(f"Worst Performing Baud Rate: {worst['rate']} bps ({worst['success_rate']:.1f}% success, BER: {worst['ber']:.2e})\n\n")

            f.write("DETAILED RESULTS\n")
            f.write("-" * 20 + "\n")

            for result in self.test_results:
                f.write(f"\nBaud Rate: {result['baud_rate']} bps\n")
                f.write(f"  Success Rate: {result['success_rate']:.1f}% ({result['successful_messages']}/{result['total_messages']})\n")
                f.write(f"  Bit Error Rate: {result['ber']:.2e}\n")
                f.write(f"  Timeout Errors: {result['timeout_errors']}\n")
                f.write(f"  Average Response Time: {result['average_response_time']:.3f}s\n")

                if result['errors']:
                    f.write(f"  Errors ({len(result['errors'])}):\n")
                    for error in result['errors'][:10]:  # Show first 10 errors
                        f.write(f"    {error}\n")
                    if len(result['errors']) > 10:
                        f.write(f"    ... and {len(result['errors']) - 10} more errors\n")

        print(f"\n\n{'='*60}")
        print("TEST COMPLETED!")
        print(f"{'='*60}")
        print(f"Reports saved:")
        print(f"  JSON: {json_filename}")
        print(f"  Text: {text_filename}")
        print(f"\nOverall Success Rate: {report['summary']['overall_success_rate']:.1f}%")
        print(f"Best Baud Rate: {best['rate']} bps ({best['success_rate']:.1f}% success)")
        print(f"Worst Baud Rate: {worst['rate']} bps ({worst['success_rate']:.1f}% success)")

def main():
    parser = argparse.ArgumentParser(description='RS485 Adapter Baud Rate Sweep Test')
    parser.add_argument('port', help='Serial port (e.g., COM3, /dev/ttyUSB0)')
    parser.add_argument('--timeout', type=float, default=2.0, help='Timeout in seconds (default: 2.0)')
    parser.add_argument('--messages', type=int, default=100, help='Messages per baud rate (default: 100)')

    args = parser.parse_args()

    try:
        tester = BaudRateSweepTest(args.port, args.timeout)
        tester.message_count = args.messages
        tester.run_sweep()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()