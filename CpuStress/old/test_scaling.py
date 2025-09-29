#!/usr/bin/env python3

# Test new scaling factors
from smbus import SMBus

def test_scaling():
    bus = SMBus(3)
    address = 0x63

    # Read raw values
    v_msb = bus.read_byte_data(address, 0x00)
    v_lsb = bus.read_byte_data(address, 0x01)
    voltage_raw = (v_msb << 8) | v_lsb

    i_msb = bus.read_byte_data(address, 0x02)
    i_lsb = bus.read_byte_data(address, 0x03)
    current_raw = (i_msb << 8) | i_lsb

    p_msb = bus.read_byte_data(address, 0x04)
    p_lsb = bus.read_byte_data(address, 0x05)
    power_raw = (p_msb << 8) | p_lsb

    # New scaling factors
    voltage_scale = 3.3 / 216      # ~0.0153 V per LSB
    current_scale = 1.5 / 20607    # ~0.000073 A per LSB
    power_scale = 5.0 / 63365      # ~0.000079 W per LSB

    # Calculate scaled values
    voltage = voltage_raw * voltage_scale
    current = current_raw * current_scale
    power_reg = power_raw * power_scale
    power_calc = voltage * current

    print("LTC2959 Scaling Test")
    print("=" * 40)
    print(f"Raw Values:")
    print(f"  Voltage: {voltage_raw:5d} → {voltage:.3f} V")
    print(f"  Current: {current_raw:5d} → {current:.3f} A")
    print(f"  Power:   {power_raw:5d} → {power_reg:.3f} W")
    print(f"")
    print(f"Calculated Power (V×I): {power_calc:.3f} W")
    print(f"Power Register Reading: {power_reg:.3f} W")
    print(f"Difference: {abs(power_calc - power_reg):.3f} W")

    # Sanity check
    if 2.0 < voltage < 5.0:
        print("✓ Voltage seems reasonable (2-5V range)")
    else:
        print("✗ Voltage may need calibration")

    if 0.5 < current < 3.0:
        print("✓ Current seems reasonable (0.5-3A range)")
    else:
        print("✗ Current may need calibration")

    if 1.0 < power_reg < 15.0:
        print("✓ Power seems reasonable (1-15W range)")
    else:
        print("✗ Power may need calibration")

if __name__ == "__main__":
    test_scaling()