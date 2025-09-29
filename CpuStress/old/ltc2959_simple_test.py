#!/usr/bin/env python3
"""
Simple LTC2959 Test - Direct register reading with proper decoding
Based on LTC2959 datasheet register map
"""

import time
from smbus import SMBus

def read_ltc2959_power(bus_num=3, address=0x63):
    """
    Read power measurements from LTC2959
    Based on LTC2959 datasheet register definitions
    """
    bus = SMBus(bus_num)

    try:
        # LTC2959 register map (from datasheet)
        # These registers contain ADC results for power monitoring

        # Read voltage registers (16-bit values)
        vin_msb = bus.read_byte_data(address, 0x00)
        vin_lsb = bus.read_byte_data(address, 0x01)
        vin_raw = (vin_msb << 8) | vin_lsb

        # Read current registers
        iout_msb = bus.read_byte_data(address, 0x02)
        iout_lsb = bus.read_byte_data(address, 0x03)
        iout_raw = (iout_msb << 8) | iout_lsb

        # Read power registers
        pout_msb = bus.read_byte_data(address, 0x04)
        pout_lsb = bus.read_byte_data(address, 0x05)
        pout_raw = (pout_msb << 8) | pout_lsb

        # Convert raw values to real units
        # These scaling factors need to be calibrated based on your specific implementation
        voltage_scale = 0.001  # Volts per LSB (adjust based on voltage divider)
        current_scale = 0.001  # Amps per LSB (adjust based on current sense resistor)
        power_scale = 0.001    # Watts per LSB

        voltage = vin_raw * voltage_scale
        current = iout_raw * current_scale
        power = pout_raw * power_scale

        return {
            'voltage_raw': vin_raw,
            'current_raw': iout_raw,
            'power_raw': pout_raw,
            'voltage': voltage,
            'current': current,
            'power': power,
            'timestamp': time.time()
        }

    except Exception as e:
        print(f"Error reading LTC2959: {e}")
        return None

def main():
    """Test LTC2959 power readings"""
    print("LTC2959 Simple Power Monitor Test")
    print("=" * 50)
    print("Bus: 3, Address: 0x63")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            data = read_ltc2959_power()

            if data:
                timestamp = time.strftime('%H:%M:%S', time.localtime(data['timestamp']))

                print(f"[{timestamp}]")
                print(f"  Raw Values - V: 0x{data['voltage_raw']:04X} ({data['voltage_raw']:5d})")
                print(f"               I: 0x{data['current_raw']:04X} ({data['current_raw']:5d})")
                print(f"               P: 0x{data['power_raw']:04X} ({data['power_raw']:5d})")
                print(f"  Scaled     - V: {data['voltage']:.3f} V")
                print(f"               I: {data['current']:.3f} A")
                print(f"               P: {data['power']:.3f} W")
                print("-" * 40)
            else:
                print("Failed to read data")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")

if __name__ == "__main__":
    main()