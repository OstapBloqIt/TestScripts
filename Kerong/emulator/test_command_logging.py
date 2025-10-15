#!/usr/bin/env python3
"""
Quick test for command logging feature in V3
"""

import sys
sys.path.insert(0, '.')

from modbus_rtu_emulator_v3 import ModbusRTUEmulator, CommandLog, crc16_bytes

def test_command_logging():
    """Test that commands are properly logged"""
    print("Testing command logging feature...")

    # Create emulator
    emulator = ModbusRTUEmulator(num_devices=1)

    # Collect logged commands
    logged_commands = []

    def log_callback(command_log):
        logged_commands.append(command_log)
        print(f"\n✓ Command logged: {command_log.function_name}")

    emulator.set_command_log_callback(log_callback)

    # Test 1: Read 48 coils
    print("\n1. Testing Read 48 Coils...")
    request = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x30])
    request += crc16_bytes(request)
    emulator._process_frame(request)

    # Test 2: Unlock lock #1
    print("\n2. Testing Unlock Lock #1...")
    request = bytes([0x00, 0x05, 0x00, 0x00, 0x00, 0x00])
    request += crc16_bytes(request)
    emulator._process_frame(request)

    # Test 3: Close lock #1
    print("\n3. Testing Close/Lock Lock #1...")
    request = bytes([0x00, 0x05, 0x00, 0x00, 0xFF, 0x00])
    request += crc16_bytes(request)
    emulator._process_frame(request)

    # Verify
    print(f"\n{'='*70}")
    print(f"Total commands logged: {len(logged_commands)}")
    print(f"{'='*70}")

    assert len(logged_commands) == 3, f"Expected 3 logged commands, got {len(logged_commands)}"

    # Display detailed log of first command
    print("\nDetailed log of first command:")
    print(logged_commands[0].format_log())

    # Verify command details
    assert logged_commands[0].function_code == 0x01, "First command should be Read Coils"
    assert logged_commands[0].device_addr == 0x00, "Device address should be 0"
    assert "48" in logged_commands[0].parameters, "Should mention 48 coils"

    assert logged_commands[1].function_code == 0x05, "Second command should be Write Single Coil"
    assert "UNLOCK" in logged_commands[1].result, "Should indicate unlock operation"

    assert logged_commands[2].function_code == 0x05, "Third command should be Write Single Coil"
    assert "CLOSED" in logged_commands[2].result, "Should indicate lock/close operation"

    print("\n✅ Command logging test PASSED!")
    print("\nLogged command summaries:")
    for i, cmd in enumerate(logged_commands, 1):
        print(f"  {i}. {cmd.function_name}: {cmd.result}")

if __name__ == "__main__":
    test_command_logging()
