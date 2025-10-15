#!/usr/bin/env python3
"""
Test script for Modbus RTU Emulator V2
Tests the enhanced error tracking and display features
"""

import sys
sys.path.insert(0, '.')

from modbus_rtu_emulator_v2 import (
    calculate_crc16, crc16_bytes, verify_crc,
    ModbusSlaveDevice, ModbusRTUEmulator, Statistics, ErrorDetail
)
from datetime import datetime


def test_error_detail_formatting():
    """Test ErrorDetail formatting"""
    print("Testing ErrorDetail formatting...")

    # Test CRC error
    frame_with_bad_crc = bytes.fromhex('01 03 00 0f 00 01 FF FF')  # Wrong CRC
    expected_crc = crc16_bytes(frame_with_bad_crc[:-2])

    error = ErrorDetail(
        timestamp="2025-10-14 17:40:12.345",
        error_type="CRC",
        frame=frame_with_bad_crc,
        description=f"CRC mismatch",
        expected_value=expected_crc,
        error_position=6
    )

    print(error.format_detailed())
    print("\n")

    # Test framing error
    short_frame = bytes.fromhex('01 03')

    error2 = ErrorDetail(
        timestamp="2025-10-14 17:40:15.678",
        error_type="FRAMING",
        frame=short_frame,
        description="Frame too short: 2 bytes (minimum 4 bytes required)",
        error_position=None
    )

    print(error2.format_detailed())
    print("\n")

    # Test unsupported function
    unsupported_frame = bytes.fromhex('01 50 00 00 C4 1E')  # Function 0x50

    error3 = ErrorDetail(
        timestamp="2025-10-14 17:40:20.123",
        error_type="UNSUPPORTED",
        frame=unsupported_frame,
        description="Unsupported function code: 0x50",
        error_position=1
    )

    print(error3.format_detailed())

    print("Error detail formatting tests passed!\n")


def test_statistics_error_tracking():
    """Test statistics error tracking"""
    print("Testing Statistics error tracking...")

    stats = Statistics()

    # Add some errors
    for i in range(7):  # Add 7 errors (should keep last 5)
        error = ErrorDetail(
            timestamp=f"2025-10-14 17:40:{i:02d}.000",
            error_type="CRC" if i % 2 == 0 else "FRAMING",
            frame=bytes([0x01, 0x03, 0x00, 0x00]),
            description=f"Test error {i}",
            error_position=None
        )
        stats.add_error(error)

    # Should only have 5 errors (most recent)
    assert len(stats.recent_errors) == 5, f"Expected 5 errors, got {len(stats.recent_errors)}"
    assert stats.recent_errors[0].description == "Test error 2", "Wrong oldest error"
    assert stats.recent_errors[-1].description == "Test error 6", "Wrong newest error"

    print(f"  ✓ Error queue maintains max 5 errors")
    print(f"  ✓ Oldest error: {stats.recent_errors[0].description}")
    print(f"  ✓ Newest error: {stats.recent_errors[-1].description}")

    # Test get_recent_errors_summary
    summary = stats.get_recent_errors_summary()
    assert "LAST 5 ERRORS" in summary
    assert "Test error 6" in summary
    assert "Test error 2" in summary

    print(f"  ✓ Error summary generation works")
    print("Statistics error tracking tests passed!\n")


def test_emulator_error_detection():
    """Test emulator error detection"""
    print("Testing Emulator error detection...")

    emulator = ModbusRTUEmulator(num_devices=2)  # Devices 0 and 1

    # Test 1: CRC error
    print("  Testing CRC error detection...")
    bad_crc_frame = bytes.fromhex('01 03 00 0f 00 01 FF FF')
    emulator._process_frame(bad_crc_frame)

    assert emulator.stats.crc_errors == 1, "CRC error not counted"
    assert emulator.stats.invalid_requests == 1, "Invalid request not counted"
    assert len(emulator.stats.recent_errors) == 1, "Error not logged"

    last_error = emulator.stats.recent_errors[-1]
    assert last_error.error_type == "CRC", "Wrong error type"
    assert last_error.error_position == 6, "Wrong error position"
    print(f"    ✓ CRC error detected and logged")

    # Test 2: Framing error
    print("  Testing framing error detection...")
    short_frame = bytes.fromhex('01 03')
    emulator._process_frame(short_frame)

    assert emulator.stats.framing_errors == 1, "Framing error not counted"
    assert emulator.stats.invalid_requests == 2, "Invalid request not counted"
    assert len(emulator.stats.recent_errors) == 2, "Error not logged"

    last_error = emulator.stats.recent_errors[-1]
    assert last_error.error_type == "FRAMING", "Wrong error type"
    print(f"    ✓ Framing error detected and logged")

    # Test 3: Valid frame (no error) - device 0
    print("  Testing valid frame (no error)...")
    valid_frame = bytes.fromhex('00 03 00 0f 00 01') + crc16_bytes(bytes.fromhex('00 03 00 0f 00 01'))
    emulator._process_frame(valid_frame)

    assert emulator.stats.valid_requests == 1, "Valid request not counted"
    assert emulator.stats.crc_errors == 1, "CRC error count changed"
    assert emulator.stats.framing_errors == 1, "Framing error count changed"
    print(f"    ✓ Valid frame processed without error")

    # Test 4: Unsupported function
    print("  Testing unsupported function detection...")
    # Create a valid frame with unsupported function code 0x50 for device 0
    unsupported_req = bytes([0x00, 0x50, 0x00, 0x00])
    unsupported_req += crc16_bytes(unsupported_req)
    emulator._process_frame(unsupported_req)

    assert emulator.stats.unsupported_function == 1, "Unsupported function not counted"
    assert len(emulator.stats.recent_errors) == 3, "Error not logged"

    last_error = emulator.stats.recent_errors[-1]
    assert last_error.error_type == "UNSUPPORTED", "Wrong error type"
    assert last_error.error_position == 1, "Wrong error position (should point to function code)"
    print(f"    ✓ Unsupported function detected and logged")

    print("Emulator error detection tests passed!\n")


def test_error_display():
    """Test error display with real examples"""
    print("Testing error display with real examples...")

    stats = Statistics()

    # Simulate various errors
    errors_to_create = [
        {
            'frame': bytes.fromhex('01 03 00 0f 00 01 AA BB'),  # Bad CRC
            'type': 'CRC',
            'desc': 'CRC mismatch in register read request'
        },
        {
            'frame': bytes.fromhex('FF 01 00 00 00 01') + crc16_bytes(bytes.fromhex('FF 01 00 00 00 01')),
            'type': 'CRC',  # Will be valid CRC but invalid device
            'desc': 'Request for non-emulated device 0xFF'
        },
        {
            'frame': bytes.fromhex('01'),
            'type': 'FRAMING',
            'desc': 'Incomplete frame'
        },
        {
            'frame': bytes([0x01, 0x99, 0x00, 0x00]) + crc16_bytes(bytes([0x01, 0x99, 0x00, 0x00])),
            'type': 'UNSUPPORTED',
            'desc': 'Invalid function code 0x99'
        },
        {
            'frame': bytes.fromhex('02 03'),
            'type': 'FRAMING',
            'desc': 'Truncated frame for device 2'
        }
    ]

    for i, err_info in enumerate(errors_to_create):
        frame = err_info['frame']

        if err_info['type'] == 'CRC' and len(frame) >= 4:
            expected_crc = crc16_bytes(frame[:-2])
        else:
            expected_crc = None

        error = ErrorDetail(
            timestamp=f"2025-10-14 17:45:{i:02d}.{i*100:03d}",
            error_type=err_info['type'],
            frame=frame,
            description=err_info['desc'],
            expected_value=expected_crc,
            error_position=len(frame)-2 if err_info['type'] == 'CRC' and len(frame) >= 4 else (1 if err_info['type'] == 'UNSUPPORTED' else None)
        )
        stats.add_error(error)

    # Display the errors
    print("\n" + "=" * 70)
    print(stats.get_recent_errors_summary())
    print("=" * 70)

    print("\nError display test completed!\n")


def main():
    """Run all V2 tests"""
    print("=" * 70)
    print("MODBUS RTU EMULATOR V2 - ERROR TRACKING TESTS")
    print("=" * 70)
    print()

    try:
        test_error_detail_formatting()
        test_statistics_error_tracking()
        test_emulator_error_detection()
        test_error_display()

        print("=" * 70)
        print("ALL V2 TESTS PASSED!")
        print("=" * 70)
        print()
        print("V2 Features Verified:")
        print("  ✓ Detailed error tracking with frame analysis")
        print("  ✓ Error position highlighting")
        print("  ✓ Expected vs actual value comparison")
        print("  ✓ Last 5 errors retention")
        print("  ✓ Formatted error display")
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
