#!/usr/bin/env python3
"""
Test script for Modbus RTU Emulator
Tests the core functionality without requiring hardware
"""

import struct
from modbus_rtu_emulator import (
    calculate_crc16, crc16_bytes, verify_crc,
    ModbusSlaveDevice, Statistics
)


def test_crc16():
    """Test CRC-16 calculation"""
    print("Testing CRC-16 calculation...")

    # Test case from the captured traffic
    # 01 01 00 00 00 01 [fd ca]
    data = bytes([0x01, 0x01, 0x00, 0x00, 0x00, 0x01])
    crc = crc16_bytes(data)
    expected_crc = bytes([0xfd, 0xca])

    assert crc == expected_crc, f"CRC mismatch: got {crc.hex()}, expected {expected_crc.hex()}"
    print(f"  ✓ CRC-16 calculation correct: {crc.hex()}")

    # Test verification
    full_message = data + crc
    assert verify_crc(full_message), "CRC verification failed"
    print(f"  ✓ CRC-16 verification correct")

    # Test another case: 01 03 00 0f 00 01 [b4 09]
    data2 = bytes([0x01, 0x03, 0x00, 0x0f, 0x00, 0x01])
    crc2 = crc16_bytes(data2)
    expected_crc2 = bytes([0xb4, 0x09])
    assert crc2 == expected_crc2, f"CRC mismatch: got {crc2.hex()}, expected {expected_crc2.hex()}"
    print(f"  ✓ CRC-16 second test correct: {crc2.hex()}")

    print("CRC-16 tests passed!\n")


def test_slave_device():
    """Test Modbus slave device functionality"""
    print("Testing Modbus Slave Device...")

    device = ModbusSlaveDevice(device_id=0)

    # Test 1: Read Coils (Function 01)
    print("  Testing Read Coils (0x01)...")
    request = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x01])
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])  # Remove CRC

    assert response is not None, "No response generated"
    assert response[0] == 0x00, "Wrong device address"
    assert response[1] == 0x01, "Wrong function code"
    assert response[2] == 0x01, "Wrong byte count"
    print(f"    ✓ Read Coils response: {response.hex()}")

    # Test 2: Read Holding Registers (Function 03)
    print("  Testing Read Holding Registers (0x03)...")
    request = bytes([0x00, 0x03, 0x00, 0x0f, 0x00, 0x01])
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[0] == 0x00, "Wrong device address"
    assert response[1] == 0x03, "Wrong function code"
    assert response[2] == 0x02, "Wrong byte count"
    # Device 0 should have 0xE230 at register 0x0F
    reg_value = struct.unpack('>H', response[3:5])[0]
    assert reg_value == 0xE230, f"Wrong register value: {reg_value:04X}"
    print(f"    ✓ Read Holding Registers response: {response.hex()}")
    print(f"    ✓ Register 0x0F value: 0x{reg_value:04X} (57904)")

    # Test 3: Read multiple registers
    print("  Testing Read Multiple Registers...")
    request = bytes([0x00, 0x03, 0x00, 0xf5, 0x00, 0x02])
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[2] == 0x04, "Wrong byte count (should be 4 for 2 registers)"
    reg1 = struct.unpack('>H', response[3:5])[0]
    reg2 = struct.unpack('>H', response[5:7])[0]
    assert reg1 == 0x0002, f"Wrong register 0xF5 value: {reg1:04X}"
    assert reg2 == 0x0004, f"Wrong register 0xF6 value: {reg2:04X}"
    print(f"    ✓ Read Multiple Registers response: {response.hex()}")
    print(f"    ✓ Register 0xF5 = 0x{reg1:04X}, Register 0xF6 = 0x{reg2:04X}")

    # Test 4: Write Single Coil (Function 05)
    print("  Testing Write Single Coil (0x05)...")
    request = bytes([0x00, 0x05, 0x00, 0x10, 0xFF, 0x00])
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[0] == 0x00, "Wrong device address"
    assert response[1] == 0x05, "Wrong function code"
    assert device.coils[0x10] == True, "Coil not set"
    print(f"    ✓ Write Single Coil response: {response.hex()}")

    # Test 5: Write Single Register (Function 06)
    print("  Testing Write Single Register (0x06)...")
    request = bytes([0x00, 0x06, 0x00, 0x20, 0x12, 0x34])
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[0] == 0x00, "Wrong device address"
    assert response[1] == 0x06, "Wrong function code"
    assert device.holding_registers[0x20] == 0x1234, "Register not written"
    print(f"    ✓ Write Single Register response: {response.hex()}")

    # Test 6: Wrong device address (should return None)
    print("  Testing Wrong Device Address...")
    request = bytes([0x01, 0x01, 0x00, 0x00, 0x00, 0x01])
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])

    assert response is None, "Device responded to wrong address!"
    print(f"    ✓ Correctly ignored request for different device")

    # Test 7: Unsupported function code
    print("  Testing Unsupported Function Code...")
    request = bytes([0x00, 0x50, 0x00, 0x00])  # Function 0x50 not supported
    request += crc16_bytes(request)
    response = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[1] & 0x80, "Should be exception response"
    assert response[2] == 0x01, "Should be illegal function exception"
    print(f"    ✓ Exception response for unsupported function: {response.hex()}")

    print("Slave device tests passed!\n")


def test_statistics():
    """Test statistics collection"""
    print("Testing Statistics...")

    stats = Statistics()

    # Simulate some traffic
    stats.total_requests = 100
    stats.valid_requests = 95
    stats.invalid_requests = 5
    stats.crc_errors = 3
    stats.framing_errors = 2
    stats.responses_sent = 95
    stats.bytes_received = 800
    stats.bytes_sent = 600

    stats.device_requests = {1: 50, 2: 45}
    stats.function_code_counts = {0x01: 60, 0x03: 35}

    summary = stats.get_summary()
    print(summary)

    assert "Total Requests:     100" in summary
    assert "Valid Requests:     95" in summary
    assert "CRC Errors:         3" in summary
    assert "Device 01" in summary
    assert "Device 02" in summary
    assert "Read Coils" in summary

    print("Statistics tests passed!\n")


def test_frame_examples():
    """Test with actual frames from the captured traffic (updated for device 0)"""
    print("Testing with captured traffic frames...")

    device = ModbusSlaveDevice(device_id=0)

    test_frames = [
        # Frame 1: Read Coil Status
        {
            'name': 'Read 1 coil at address 0',
            'request': bytes.fromhex('00 01 00 00 00 01') + crc16_bytes(bytes.fromhex('00 01 00 00 00 01')),
            'expected_func': 0x01
        },
        # Frame 2: Read Holding Register at 0x0F
        {
            'name': 'Read 1 register at address 0x0F',
            'request': bytes.fromhex('00 03 00 0f 00 01') + crc16_bytes(bytes.fromhex('00 03 00 0f 00 01')),
            'expected_func': 0x03,
            'expected_value': 0xE230
        },
        # Frame 3: Read 2 registers at 0xF5
        {
            'name': 'Read 2 registers at address 0xF5',
            'request': bytes.fromhex('00 03 00 f5 00 02') + crc16_bytes(bytes.fromhex('00 03 00 f5 00 02')),
            'expected_func': 0x03
        },
        # Frame 4: Read 48 coils
        {
            'name': 'Read 48 coils at address 0',
            'request': bytes.fromhex('00 01 00 00 00 30') + crc16_bytes(bytes.fromhex('00 01 00 00 00 30')),
            'expected_func': 0x01
        }
    ]

    for i, frame in enumerate(test_frames, 1):
        print(f"  Test {i}: {frame['name']}")

        # Verify CRC
        assert verify_crc(frame['request']), f"CRC verification failed for frame {i}"

        # Process request
        response = device.process_request(frame['request'][:-2])
        assert response is not None, f"No response for frame {i}"

        # Verify function code
        assert response[1] == frame['expected_func'], \
            f"Wrong function code in response {i}: {response[1]:02X}"

        # Verify CRC of response
        assert verify_crc(response), f"Response CRC invalid for frame {i}"

        print(f"    Request:  {frame['request'].hex()}")
        print(f"    Response: {response.hex()}")
        print(f"    ✓ Passed")

    print("Captured traffic tests passed!\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("MODBUS RTU EMULATOR - UNIT TESTS")
    print("=" * 60)
    print()

    try:
        test_crc16()
        test_slave_device()
        test_statistics()
        test_frame_examples()

        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
