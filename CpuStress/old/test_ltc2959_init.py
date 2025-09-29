#!/usr/bin/env python3

# Quick test of the LTC2959 initialization
from smbus import SMBus

class LTC2959Test:
    def __init__(self, bus_number=3, address=0x63):
        self.bus_number = bus_number
        self.address = address
        self.bus = SMBus(bus_number)

        # Register addresses
        self.REG_VSENSE_H = 0x00
        self.REG_VSENSE_L = 0x01
        self.REG_ISENSE_H = 0x02
        self.REG_ISENSE_L = 0x03
        self.REG_POWER_H = 0x04
        self.REG_POWER_L = 0x05

    def read_register(self, register):
        try:
            return self.bus.read_byte_data(self.address, register)
        except Exception as e:
            print(f"Error reading register 0x{register:02X}: {e}")
            return None

    def read_16bit_register(self, msb_reg, lsb_reg):
        try:
            msb = self.bus.read_byte_data(self.address, msb_reg)
            lsb = self.bus.read_byte_data(self.address, lsb_reg)
            return (msb << 8) | lsb
        except Exception as e:
            print(f"Error reading registers 0x{msb_reg:02X}/0x{lsb_reg:02X}: {e}")
            return None

    def write_register(self, register, value):
        try:
            self.bus.write_byte_data(self.address, register, value)
            print(f"Wrote 0x{value:02X} to register 0x{register:02X}")
            return True
        except Exception as e:
            print(f"Error writing register 0x{register:02X}: {e}")
            return False

    def analyze_chip_state(self):
        print("LTC2959: Analyzing chip state...")

        # Read all registers
        for reg in range(0x10):
            value = self.read_register(reg)
            if value is not None:
                print(f"  Reg 0x{reg:02X}: 0x{value:02X} ({value:3d})")

        print("\nChecking for data changes...")

        # Read voltage/current twice
        v1 = self.read_16bit_register(self.REG_VSENSE_H, self.REG_VSENSE_L)
        i1 = self.read_16bit_register(self.REG_ISENSE_H, self.REG_ISENSE_L)
        p1 = self.read_16bit_register(self.REG_POWER_H, self.REG_POWER_L)

        import time
        time.sleep(0.1)

        v2 = self.read_16bit_register(self.REG_VSENSE_H, self.REG_VSENSE_L)
        i2 = self.read_16bit_register(self.REG_ISENSE_H, self.REG_ISENSE_L)
        p2 = self.read_16bit_register(self.REG_POWER_H, self.REG_POWER_L)

        print(f"First reading  - V: 0x{v1:04X} ({v1:5d}), I: 0x{i1:04X} ({i1:5d}), P: 0x{p1:04X} ({p1:5d})")
        print(f"Second reading - V: 0x{v2:04X} ({v2:5d}), I: 0x{i2:04X} ({i2:5d}), P: 0x{p2:04X} ({p2:5d})")

        if v1 != v2 or i1 != i2 or p1 != p2:
            print("✓ Data is changing - chip is in continuous measurement mode")
            return True
        else:
            print("✗ Data is static - trying to enable measurements")
            return self.try_enable_measurements()

    def try_enable_measurements(self):
        print("\nTrying to enable measurements...")
        import time

        # Try common control register values
        control_registers = [0x07, 0x06, 0x08, 0x09]
        enable_values = [0x01, 0x80, 0x03, 0x07]

        for reg in control_registers:
            for val in enable_values:
                print(f"Trying reg 0x{reg:02X} = 0x{val:02X}")
                if self.write_register(reg, val):
                    time.sleep(0.01)
                    # Check if data changes now
                    v1 = self.read_16bit_register(self.REG_VSENSE_H, self.REG_VSENSE_L)
                    time.sleep(0.05)
                    v2 = self.read_16bit_register(self.REG_VSENSE_H, self.REG_VSENSE_L)
                    if v1 != v2:
                        print(f"✓ Success! Reg 0x{reg:02X} = 0x{val:02X} enabled measurements")
                        return True

        print("Could not enable measurements, using current state")
        return True  # Accept current state

if __name__ == "__main__":
    ltc = LTC2959Test()
    ltc.analyze_chip_state()