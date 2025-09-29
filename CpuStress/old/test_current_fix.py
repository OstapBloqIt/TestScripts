#!/usr/bin/env python3

# Test current readings with corrected 10mΩ sense resistor
from smbus import SMBus
import time

def test_current_readings():
    bus = SMBus(3)
    address = 0x63

    # LTC2959 current registers (from datasheet)
    REG_CURRENT_MSB = 0x19  # Current MSB (register Z) - signed
    REG_CURRENT_LSB = 0x1A  # Current LSB (register AA) - signed

    # Scaling factors with corrected 10mΩ sense resistor
    current_lsb = 97.5e-3 / 32768          # 2.975 µV per LSB (signed, from datasheet)
    sense_resistor = 0.010                 # 10mΩ sense resistor (0.010Ω, 1W, 1%)
    current_scale = current_lsb / sense_resistor  # A per LSB

    print("LTC2959 Current Test with 10mΩ Sense Resistor")
    print("=" * 50)
    print(f"Current LSB: {current_lsb*1e6:.3f} µV per LSB")
    print(f"Sense Resistor: {sense_resistor*1000:.1f} mΩ")
    print(f"Current Scale: {current_scale:.6f} A per LSB")
    print()

    for i in range(10):
        try:
            # Read current (signed 16-bit)
            msb = bus.read_byte_data(address, REG_CURRENT_MSB)
            lsb = bus.read_byte_data(address, REG_CURRENT_LSB)
            raw_value = (msb << 8) | lsb

            # Convert to signed 16-bit value (two's complement)
            if raw_value > 32767:  # If MSB is set (negative value)
                signed_raw = raw_value - 65536
            else:
                signed_raw = raw_value

            # Apply current scaling
            current_amps = signed_raw * current_scale

            print(f"Reading {i+1}: Raw=0x{raw_value:04X} ({signed_raw:6d}) → {current_amps:+6.3f} A")
            time.sleep(0.5)

        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    test_current_readings()