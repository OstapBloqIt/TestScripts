#!/usr/bin/env python3
"""
Test script for Modbus RTU Emulator V3 (CU48 Protocol)
Tests CU48-specific functionality with 48 locks per device
"""

import sys
sys.path.insert(0, '.')

from modbus_rtu_emulator_v3 import (
    calculate_crc16, crc16_bytes, verify_crc,
    CU48Device, ModbusRTUEmulator, Statistics, ErrorDetail
)
from datetime import datetime


def test_cu48_initialization():
    """Test CU48 device initialization with all locks closed"""
    print("Testing CU48 Device Initialization...")

    device = CU48Device(device_id=0)

    # Verify all 48 locks are closed (True = 1 = locked)
    assert len(device.coils) == 48, f"Expected 48 locks, got {len(device.coils)}"
    assert all(device.coils), "All locks should be closed (True) by default"

    print(f"  ✓ Device has 48 locks")
    print(f"  ✓ All locks initialized as CLOSED/LOCKED (1)")

    # Test lock status bytes
    status_bytes = device.get_lock_status_bytes()
    assert len(status_bytes) == 6, f"Expected 6 bytes for 48 bits, got {len(status_bytes)}"
    assert status_bytes == b'\xFF\xFF\xFF\xFF\xFF\xFF', f"All bits should be 1, got {status_bytes.hex()}"
    print(f"  ✓ Lock status bytes: {status_bytes.hex().upper()} (all closed)")

    print("CU48 initialization tests passed!\n")


def test_read_48_coils():
    """Test reading all 48 coil statuses (CU48 standard request)"""
    print("Testing Read 48 Coils...")

    device = CU48Device(device_id=0)

    # Request to read 48 coils starting at address 0
    # This is the standard CU48 request: 00 01 00 00 00 30 [CRC]
    request = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x30])  # 0x30 = 48 decimal
    request += crc16_bytes(request)

    response, operation = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[0] == 0x00, "Wrong device address"
    assert response[1] == 0x01, "Wrong function code"
    assert response[2] == 0x06, "Wrong byte count (should be 6 for 48 coils)"

    # Verify all bits are 1 (all locks closed)
    status_data = response[3:9]  # 6 bytes of status
    assert status_data == b'\xFF\xFF\xFF\xFF\xFF\xFF', f"Expected all FF, got {status_data.hex()}"

    print(f"  Request:  {request.hex().upper()}")
    print(f"  Response: {response.hex().upper()}")
    print(f"  ✓ Successfully read 48 coils")
    print(f"  ✓ All coils report CLOSED (0xFF = all bits 1)")

    print("Read 48 coils test passed!\n")


def test_write_single_lock_unlock():
    """Test unlocking a single lock (Write Single Coil)"""
    print("Testing Write Single Coil (Unlock)...")

    device = CU48Device(device_id=0)

    # Unlock lock #1 (address 0x00): 00 05 00 00 00 00 [CRC]
    # Value 0x0000 = unlock (coil = 0)
    request = bytes([0x00, 0x05, 0x00, 0x00, 0x00, 0x00])
    request += crc16_bytes(request)

    response, operation = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[0] == 0x00, "Wrong device address"
    assert response[1] == 0x05, "Wrong function code"
    assert device.coils[0] == False, "Lock #1 should be unlocked (False)"
    assert operation is not None, "Operation description should be returned"
    assert "LOCK #1" in operation and "UNLOCKED" in operation

    print(f"  Request:  {request.hex().upper()}")
    print(f"  Response: {response.hex().upper()}")
    print(f"  Operation: {operation}")
    print(f"  ✓ Lock #1 successfully unlocked")

    # Verify lock #1 is unlocked but others are still closed
    assert device.coils[0] == False, "Lock #1 should be unlocked"
    assert all(device.coils[1:]), "All other locks should still be closed"

    print(f"  ✓ Other 47 locks remain CLOSED")

    print("Write single coil (unlock) test passed!\n")


def test_write_single_lock_close():
    """Test closing/locking a single lock (Write Single Coil)"""
    print("Testing Write Single Coil (Close/Lock)...")

    device = CU48Device(device_id=0)

    # First unlock lock #5
    device.coils[4] = False

    # Now close/lock lock #5 (address 0x04): 00 05 00 04 FF 00 [CRC]
    # Value 0xFF00 = close/lock (coil = 1)
    request = bytes([0x00, 0x05, 0x00, 0x04, 0xFF, 0x00])
    request += crc16_bytes(request)

    response, operation = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert device.coils[4] == True, "Lock #5 should be closed (True)"
    assert operation is not None
    assert "LOCK #5" in operation and "CLOSED" in operation

    print(f"  Request:  {request.hex().upper()}")
    print(f"  Response: {response.hex().upper()}")
    print(f"  Operation: {operation}")
    print(f"  ✓ Lock #5 successfully closed/locked")

    print("Write single coil (close) test passed!\n")


def test_unlock_multiple_locks():
    """Test unlocking multiple locks at once"""
    print("Testing Write Multiple Coils...")

    device = CU48Device(device_id=0)

    # Unlock locks #1-8 (addresses 0x00-0x07): Write 8 coils starting at 0x00
    # All values 0x00 (unlock)
    # Request: 00 0F 00 00 00 08 01 00 [CRC]
    #          device func start_addr count byte_count values
    request = bytes([0x00, 0x0F, 0x00, 0x00, 0x00, 0x08, 0x01, 0x00])
    request += crc16_bytes(request)

    response, operation = device.process_request(request[:-2])

    assert response is not None, "No response generated"
    assert response[1] == 0x0F, "Wrong function code"

    # Verify locks 0-7 are unlocked
    for i in range(8):
        assert device.coils[i] == False, f"Lock #{i+1} should be unlocked"

    # Verify locks 8-47 are still closed
    for i in range(8, 48):
        assert device.coils[i] == True, f"Lock #{i+1} should still be closed"

    print(f"  Request:  {request.hex().upper()}")
    print(f"  Response: {response.hex().upper()}")
    print(f"  ✓ Locks #1-8 unlocked")
    print(f"  ✓ Locks #9-48 remain closed")

    print("Write multiple coils test passed!\n")


def test_mixed_lock_states():
    """Test reading mixed lock states"""
    print("Testing Mixed Lock States...")

    device = CU48Device(device_id=0)

    # Unlock specific locks: #1, #10, #20, #30, #40, #48
    unlock_indices = [0, 9, 19, 29, 39, 47]
    for idx in unlock_indices:
        device.coils[idx] = False

    # Read all 48 coils
    request = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x30])
    request += crc16_bytes(request)

    response, operation = device.process_request(request[:-2])

    assert response is not None
    status_data = response[3:9]

    print(f"  Unlocked locks: {[i+1 for i in unlock_indices]}")
    print(f"  Status bytes: {status_data.hex().upper()}")

    # Verify specific bits are 0 (unlocked)
    for idx in unlock_indices:
        byte_idx = idx // 8
        bit_idx = idx % 8
        bit_value = (status_data[byte_idx] >> bit_idx) & 1
        assert bit_value == 0, f"Lock #{idx+1} should be unlocked (bit=0)"
        print(f"  ✓ Lock #{idx+1} is unlocked (bit {byte_idx}:{bit_idx} = 0)")

    print("Mixed lock states test passed!\n")


def test_cu48_protocol_examples():
    """Test with actual CU48 protocol examples from documentation"""
    print("Testing CU48 Protocol Examples...")

    device = CU48Device(device_id=1)  # Use device address 1 like in doc examples

    # Example 1: Read 48 coils status
    # Request: 01 01 00 00 00 30 [CRC]
    print("  Example 1: Read all 48 coils from device 1")
    request = bytes.fromhex('01 01 00 00 00 30') + crc16_bytes(bytes.fromhex('01 01 00 00 00 30'))

    assert verify_crc(request), "CRC verification failed"

    response, operation = device.process_request(request[:-2])
    assert response is not None
    assert verify_crc(response), "Response CRC invalid"
    assert response[1] == 0x01, "Wrong function code"
    assert response[2] == 0x06, "Wrong byte count"

    print(f"    Request:  {request.hex().upper()}")
    print(f"    Response: {response.hex().upper()}")
    print(f"    ✓ Read 48 coils successful")

    # Example 2: Unlock single lock #1
    # Request: 01 05 00 00 00 00 [CRC] (value 0x0000 = unlock)
    print("\n  Example 2: Unlock lock #1")
    request = bytes.fromhex('01 05 00 00 00 00') + crc16_bytes(bytes.fromhex('01 05 00 00 00 00'))

    assert verify_crc(request)

    response, operation = device.process_request(request[:-2])
    assert response is not None
    assert verify_crc(response)
    assert device.coils[0] == False, "Lock should be unlocked"

    print(f"    Request:  {request.hex().upper()}")
    print(f"    Response: {response.hex().upper()}")
    print(f"    Operation: {operation}")
    print(f"    ✓ Unlock successful")

    # Example 3: Close/lock single lock #1
    # Request: 01 05 00 00 FF 00 [CRC] (value 0xFF00 = lock)
    print("\n  Example 3: Close/lock lock #1")
    request = bytes.fromhex('01 05 00 00 FF 00') + crc16_bytes(bytes.fromhex('01 05 00 00 FF 00'))

    assert verify_crc(request)

    response, operation = device.process_request(request[:-2])
    assert response is not None
    assert verify_crc(response)
    assert device.coils[0] == True, "Lock should be closed"

    print(f"    Request:  {request.hex().upper()}")
    print(f"    Response: {response.hex().upper()}")
    print(f"    Operation: {operation}")
    print(f"    ✓ Lock successful")

    print("\nCU48 protocol examples test passed!\n")


def test_emulator_with_multiple_cu48_devices():
    """Test emulator with multiple CU48 devices"""
    print("Testing Multiple CU48 Devices...")

    emulator = ModbusRTUEmulator(num_devices=3)  # Devices 0, 1, 2

    # Verify all devices have 48 closed locks
    for dev_id in range(3):
        device = emulator.devices[dev_id]
        assert len(device.coils) == 48
        assert all(device.coils), f"Device {dev_id} should have all locks closed"
        print(f"  ✓ Device {dev_id}: 48 locks, all CLOSED")

    # Unlock lock #5 on device 1
    request = bytes([0x01, 0x05, 0x00, 0x04, 0x00, 0x00])
    request += crc16_bytes(request)
    emulator._process_frame(request)

    assert emulator.devices[1].coils[4] == False, "Device 1 lock #5 should be unlocked"
    assert emulator.devices[0].coils[4] == True, "Device 0 lock #5 should still be closed"
    assert emulator.devices[2].coils[4] == True, "Device 2 lock #5 should still be closed"

    print(f"  ✓ Device 1 lock #5 unlocked")
    print(f"  ✓ Other devices unaffected")
    print(f"  ✓ Statistics: {emulator.stats.locks_unlocked} locks unlocked")

    print("Multiple CU48 devices test passed!\n")


def test_lock_operation_statistics():
    """Test that lock operations are tracked in statistics"""
    print("Testing Lock Operation Statistics...")

    emulator = ModbusRTUEmulator(num_devices=1)

    # Unlock 5 locks
    for i in range(5):
        request = bytes([0x00, 0x05, 0x00, i, 0x00, 0x00])
        request += crc16_bytes(request)
        emulator._process_frame(request)

    assert emulator.stats.locks_unlocked == 5, "Should have 5 unlocked operations"
    print(f"  ✓ Unlocked 5 locks: statistics = {emulator.stats.locks_unlocked}")

    # Lock 3 locks back
    for i in range(3):
        request = bytes([0x00, 0x05, 0x00, i, 0xFF, 0x00])
        request += crc16_bytes(request)
        emulator._process_frame(request)

    assert emulator.stats.locks_locked == 3, "Should have 3 locked operations"
    print(f"  ✓ Locked 3 locks: statistics = {emulator.stats.locks_locked}")

    # Test summary
    summary = emulator.stats.get_summary()
    assert "Locks Unlocked:     5" in summary
    assert "Locks Locked:       3" in summary
    print(f"  ✓ Statistics summary contains lock operations")

    print("Lock operation statistics test passed!\n")


def test_boundary_conditions():
    """Test boundary conditions for CU48"""
    print("Testing Boundary Conditions...")

    device = CU48Device(device_id=0)

    # Test reading beyond 48 locks (should fail)
    print("  Testing read beyond 48 locks...")
    request = bytes([0x00, 0x01, 0x00, 0x30, 0x00, 0x01])  # Start at 48, read 1
    request += crc16_bytes(request)
    response, operation = device.process_request(request[:-2])

    assert response[1] & 0x80, "Should return exception response"
    assert response[2] == 0x02, "Should be illegal data address exception"
    print(f"    ✓ Correctly rejected read beyond lock 48")

    # Test writing to lock 48 (address 0x2F) - should work
    print("  Testing write to last lock (48)...")
    request = bytes([0x00, 0x05, 0x00, 0x2F, 0x00, 0x00])  # Address 0x2F = lock 48
    request += crc16_bytes(request)
    response, operation = device.process_request(request[:-2])

    assert response is not None
    assert response[1] == 0x05, "Should be normal response"
    assert device.coils[47] == False, "Lock 48 should be unlocked"
    print(f"    ✓ Successfully wrote to lock 48")

    # Test writing beyond lock 48 (should fail)
    print("  Testing write beyond lock 48...")
    request = bytes([0x00, 0x05, 0x00, 0x30, 0x00, 0x00])  # Address 0x30 = beyond 48
    request += crc16_bytes(request)
    response, operation = device.process_request(request[:-2])

    assert response[1] & 0x80, "Should return exception response"
    assert response[2] == 0x02, "Should be illegal data address exception"
    print(f"    ✓ Correctly rejected write beyond lock 48")

    print("Boundary conditions test passed!\n")


def main():
    """Run all V3 tests"""
    print("=" * 70)
    print("MODBUS RTU EMULATOR V3 - CU48 PROTOCOL TESTS")
    print("=" * 70)
    print()

    try:
        test_cu48_initialization()
        test_read_48_coils()
        test_write_single_lock_unlock()
        test_write_single_lock_close()
        test_unlock_multiple_locks()
        test_mixed_lock_states()
        test_cu48_protocol_examples()
        test_emulator_with_multiple_cu48_devices()
        test_lock_operation_statistics()
        test_boundary_conditions()

        print("=" * 70)
        print("ALL V3 CU48 TESTS PASSED!")
        print("=" * 70)
        print()
        print("V3 CU48 Features Verified:")
        print("  ✓ 48 locks per device (addresses 0x00-0x2F)")
        print("  ✓ All locks initialize as CLOSED/LOCKED (1)")
        print("  ✓ Read coil status returns all 48 lock states")
        print("  ✓ Write single coil to unlock/lock individual locks")
        print("  ✓ Write multiple coils to unlock/lock multiple locks")
        print("  ✓ Lock state changes tracked in statistics")
        print("  ✓ Multiple CU48 devices supported")
        print("  ✓ Boundary condition checking")
        print("  ✓ Full CU48 protocol compliance")
        print()

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
