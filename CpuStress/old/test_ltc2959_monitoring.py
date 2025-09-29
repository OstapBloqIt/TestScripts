#!/usr/bin/env python3

# Monitor LTC2959 data over time to see if it changes
from smbus import SMBus
import time

class LTC2959Monitor:
    def __init__(self, bus_number=3, address=0x63):
        self.bus = SMBus(bus_number)
        self.address = address

    def read_all_data(self):
        try:
            # Read voltage (registers 0x00-0x01)
            v_msb = self.bus.read_byte_data(self.address, 0x00)
            v_lsb = self.bus.read_byte_data(self.address, 0x01)
            voltage_raw = (v_msb << 8) | v_lsb

            # Read current (registers 0x02-0x03)
            i_msb = self.bus.read_byte_data(self.address, 0x02)
            i_lsb = self.bus.read_byte_data(self.address, 0x03)
            current_raw = (i_msb << 8) | i_lsb

            # Read power (registers 0x04-0x05)
            p_msb = self.bus.read_byte_data(self.address, 0x04)
            p_lsb = self.bus.read_byte_data(self.address, 0x05)
            power_raw = (p_msb << 8) | p_lsb

            return voltage_raw, current_raw, power_raw
        except Exception as e:
            print(f"Error reading data: {e}")
            return None, None, None

    def monitor_continuous(self, duration=30, interval=0.5):
        print(f"Monitoring LTC2959 for {duration} seconds...")
        print("Time     | Voltage  | Current  | Power    | Changes")
        print("-" * 55)

        start_time = time.time()
        prev_v, prev_i, prev_p = None, None, None

        while time.time() - start_time < duration:
            v, i, p = self.read_all_data()

            if v is not None:
                changes = []
                if prev_v is not None:
                    if v != prev_v:
                        changes.append(f"V:{prev_v}→{v}")
                    if i != prev_i:
                        changes.append(f"I:{prev_i}→{i}")
                    if p != prev_p:
                        changes.append(f"P:{prev_p}→{p}")

                elapsed = time.time() - start_time
                change_str = " ".join(changes) if changes else "No changes"

                print(f"{elapsed:7.1f}s | {v:8d} | {i:8d} | {p:8d} | {change_str}")

                prev_v, prev_i, prev_p = v, i, p

            time.sleep(interval)

if __name__ == "__main__":
    monitor = LTC2959Monitor()

    print("Starting continuous monitoring...")
    print("This will show if the LTC2959 data changes over time")
    print("If data changes, the chip is working in continuous mode")
    print()

    monitor.monitor_continuous(duration=15, interval=1.0)