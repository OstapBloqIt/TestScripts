#!/usr/bin/env python3
"""
LTC2959IDDBTRMPBF Power Monitor Proof of Concept
I2C-based power monitoring chip for voltage, current, and power measurements
"""

import time
import struct
from smbus import SMBus

class LTC2959:
    def __init__(self, bus_number=3, address=0x63):
        """
        Initialize LTC2959 power monitor

        Args:
            bus_number: I2C bus number (default: 1)
            address: I2C address of LTC2959 (default: 0x50)
        """
        self.bus = SMBus(bus_number)
        self.address = address

        # LTC2959 Register addresses (based on datasheet)
        self.REG_VOLTAGE = 0x00    # Voltage measurement register
        self.REG_CURRENT = 0x01    # Current measurement register
        self.REG_POWER = 0x02      # Power calculation register
        self.REG_CONFIG = 0x03     # Configuration register
        self.REG_STATUS = 0x04     # Status register

        # Calibration factors (these may need adjustment based on actual hardware)
        self.voltage_scale = 1.0   # V per LSB
        self.current_scale = 1.0   # A per LSB
        self.power_scale = 1.0     # W per LSB

    def read_register(self, register, length=2):
        """Read data from LTC2959 register"""
        try:
            if length == 1:
                value = self.bus.read_byte_data(self.address, register)
                print(f"Read register 0x{register:02X}: 0x{value:02X}")
                return value
            elif length == 2:
                # Try reading as 16-bit value
                try:
                    data = self.bus.read_i2c_block_data(self.address, register, length)
                    value = (data[1] << 8) | data[0]
                    print(f"Read register 0x{register:02X}: 0x{value:04X} ({data})")
                    return value
                except:
                    # Fallback to byte reads
                    low = self.bus.read_byte_data(self.address, register)
                    high = self.bus.read_byte_data(self.address, register + 1)
                    value = (high << 8) | low
                    print(f"Read register 0x{register:02X}: 0x{value:04X} (bytes: {low}, {high})")
                    return value
            else:
                data = self.bus.read_i2c_block_data(self.address, register, length)
                print(f"Read register 0x{register:02X}: {data}")
                return data
        except Exception as e:
            print(f"Error reading register 0x{register:02X}: {e}")
            return None

    def write_register(self, register, value, length=1):
        """Write data to LTC2959 register"""
        try:
            if length == 1:
                self.bus.write_byte_data(self.address, register, value)
            elif length == 2:
                # Write 16-bit value (little endian)
                low_byte = value & 0xFF
                high_byte = (value >> 8) & 0xFF
                self.bus.write_i2c_block_data(self.address, register, [low_byte, high_byte])
            return True
        except Exception as e:
            print(f"Error writing register 0x{register:02X}: {e}")
            return False

    def initialize(self):
        """Initialize the LTC2959 chip"""
        print("Initializing LTC2959...")

        # Try to read status register to verify communication
        status = self.read_register(self.REG_STATUS, 1)
        if status is not None:
            print(f"LTC2959 Status: 0x{status:02X}")
            return True
        else:
            print("Failed to communicate with LTC2959")
            return False

    def read_voltage(self):
        """Read voltage measurement in Volts"""
        raw_value = self.read_register(self.REG_VOLTAGE)
        if raw_value is not None:
            voltage = raw_value * self.voltage_scale
            return voltage
        return None

    def read_current(self):
        """Read current measurement in Amperes"""
        raw_value = self.read_register(self.REG_CURRENT)
        if raw_value is not None:
            current = raw_value * self.current_scale
            return current
        return None

    def read_power(self):
        """Read power measurement in Watts"""
        raw_value = self.read_register(self.REG_POWER)
        if raw_value is not None:
            power = raw_value * self.power_scale
            return power
        return None

    def get_measurements(self):
        """Get all measurements as a dictionary"""
        return {
            'voltage': self.read_voltage(),
            'current': self.read_current(),
            'power': self.read_power(),
            'timestamp': time.time()
        }

    def calibrate(self, known_voltage=None, known_current=None, known_power=None):
        """
        Calibrate the sensor readings with known values
        This should be called with known reference values
        """
        if known_voltage:
            raw_v = self.read_register(self.REG_VOLTAGE)
            if raw_v and raw_v > 0:
                self.voltage_scale = known_voltage / raw_v
                print(f"Voltage calibrated: scale = {self.voltage_scale}")

        if known_current:
            raw_i = self.read_register(self.REG_CURRENT)
            if raw_i and raw_i > 0:
                self.current_scale = known_current / raw_i
                print(f"Current calibrated: scale = {self.current_scale}")

        if known_power:
            raw_p = self.read_register(self.REG_POWER)
            if raw_p and raw_p > 0:
                self.power_scale = known_power / raw_p
                print(f"Power calibrated: scale = {self.power_scale}")

def main():
    """Test the LTC2959 power monitor"""
    print("LTC2959 Power Monitor Test")
    print("=" * 40)

    try:
        # Initialize the power monitor
        ltc = LTC2959(bus_number=3, address=0x63)

        if not ltc.initialize():
            print("Failed to initialize LTC2959. Check connections and address.")
            return

        print("LTC2959 initialized successfully!")
        print("\nStarting measurements...")
        print("Press Ctrl+C to stop\n")

        # Take continuous measurements
        while True:
            measurements = ltc.get_measurements()

            print(f"Time: {time.strftime('%H:%M:%S', time.localtime(measurements['timestamp']))}")
            print(f"Voltage: {measurements['voltage']:.3f} V")
            print(f"Current: {measurements['current']:.3f} A")
            print(f"Power:   {measurements['power']:.3f} W")
            print("-" * 30)

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping measurements...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()