#!/usr/bin/env python3
"""
Modbus RTU Slave Emulator for Windows - Version 3 (CU48 Protocol) - FIXED
Changes vs v3:
- Robust frame boundary detection with dynamic 3.5 char times using current baudrate
- Split and process multiple frames present in the buffer (avoid merged-frame CRC false errors)
- Centralized response builder to ensure consistent normal/exception wrapping
- Uniform register initialization for all devices for consistent reads
- Minor safety/clarity tweaks
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import deque
import struct

# CRC-16 for Modbus RTU
def calculate_crc16(data: bytes) -> int:
    """Calculate Modbus RTU CRC-16"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def crc16_bytes(data: bytes) -> bytes:
    """Return CRC-16 as low-high byte order"""
    crc = calculate_crc16(data)
    return struct.pack('<H', crc)  # Little-endian (low byte first)

def verify_crc(message: bytes) -> bool:
    """Verify CRC-16 of a Modbus message"""
    if len(message) < 4:
        return False
    data = message[:-2]
    received_crc = message[-2:]
    calculated_crc = crc16_bytes(data)
    return received_crc == calculated_crc


@dataclass
class ErrorDetail:
    """Detailed information about a communication error"""
    timestamp: str
    error_type: str  # "CRC", "FRAMING", "TIMEOUT", "UNSUPPORTED"
    frame: bytes
    description: str
    expected_value: Optional[bytes] = None
    error_position: Optional[int] = None

    def format_detailed(self) -> str:
        """Format error with detailed byte-by-byte analysis"""
        lines = [
            f"[{self.timestamp}] {self.error_type} ERROR",
            f"Description: {self.description}",
            f"",
            f"Received Frame ({len(self.frame)} bytes):"
        ]

        # Show frame in hex with position markers
        hex_line = "  "
        pos_line = "  "

        for i, byte in enumerate(self.frame):
            if self.error_position is not None and i == self.error_position:
                hex_line += f"[{byte:02X}] "
                pos_line += " ^^  "
            else:
                hex_line += f" {byte:02X}  "
                pos_line += "     "

        lines.append(hex_line)
        if self.error_position is not None:
            lines.append(pos_line)
            lines.append(f"  Error at byte position {self.error_position}")

        # Decode frame structure
        lines.append(f"")
        lines.append(f"Frame Analysis:")

        if len(self.frame) >= 1:
            lines.append(f"  Device Address: 0x{self.frame[0]:02X} ({self.frame[0]})")

        if len(self.frame) >= 2:
            func_code = self.frame[1]
            func_name = {
                0x01: "Read Coils",
                0x02: "Read Discrete Inputs",
                0x03: "Read Holding Registers",
                0x04: "Read Input Registers",
                0x05: "Write Single Coil",
                0x06: "Write Single Register",
                0x0F: "Write Multiple Coils",
                0x10: "Write Multiple Registers"
            }.get(func_code & 0x7F, f"Unknown/Invalid")
            lines.append(f"  Function Code:  0x{func_code:02X} ({func_name})")

        if len(self.frame) >= 4:
            if self.error_type == "CRC":
                received_crc = self.frame[-2:]
                expected_crc = self.expected_value if self.expected_value else b'\x00\x00'
                lines.append(f"  Received CRC:   {received_crc.hex().upper()} (bytes {len(self.frame)-2}:{len(self.frame)})")
                lines.append(f"  Expected CRC:   {expected_crc.hex().upper()}")
                lines.append(f"  CRC Difference: MISMATCH")
            else:
                crc = self.frame[-2:]
                lines.append(f"  CRC-16:         {crc.hex().upper()}")

        if self.expected_value and self.error_type != "CRC":
            lines.append(f"")
            lines.append(f"Expected Value: {self.expected_value.hex().upper()}")

        lines.append("=" * 70)

        return "\n".join(lines)


@dataclass
class Statistics:
    """Statistics for Modbus communication"""
    total_requests: int = 0
    valid_requests: int = 0
    invalid_requests: int = 0
    crc_errors: int = 0
    framing_errors: int = 0
    timeout_errors: int = 0
    unsupported_function: int = 0
    responses_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    start_time: float = field(default_factory=time.time)

    # Per-device statistics
    device_requests: Dict[int, int] = field(default_factory=dict)
    function_code_counts: Dict[int, int] = field(default_factory=dict)

    # Error tracking (last 5 errors)
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=5))

    # CU48-specific stats
    locks_unlocked: int = 0
    locks_locked: int = 0

    def add_error(self, error: 'ErrorDetail'):
        """Add an error to the recent errors list"""
        self.recent_errors.append(error)

    def reset(self):
        """Reset all statistics"""
        self.__init__()

    def get_summary(self) -> str:
        """Get formatted statistics summary"""
        elapsed = time.time() - self.start_time
        lines = [
            "=" * 60,
            "MODBUS RTU SLAVE EMULATOR V3 - STATISTICS (CU48)",
            "=" * 60,
            f"Runtime: {elapsed:.1f} seconds",
            f"",
            f"REQUESTS:",
            f"  Total Requests:     {self.total_requests}",
            f"  Valid Requests:     {self.valid_requests}",
            f"  Invalid Requests:   {self.invalid_requests}",
            f"  Responses Sent:     {self.responses_sent}",
            f"",
            f"ERRORS:",
            f"  CRC Errors:         {self.crc_errors}",
            f"  Framing Errors:     {self.framing_errors}",
            f"  Timeout Errors:     {self.timeout_errors}",
            f"  Unsupported Func:   {self.unsupported_function}",
            f"",
            f"CU48 LOCK OPERATIONS:",
            f"  Locks Unlocked:     {self.locks_unlocked}",
            f"  Locks Locked:       {self.locks_locked}",
            f"",
            f"DATA TRANSFER:",
            f"  Bytes Received:     {self.bytes_received}",
            f"  Bytes Sent:         {self.bytes_sent}",
            f"",
            f"PER-DEVICE REQUESTS:"
        ]

        for device_id in sorted(self.device_requests.keys()):
            lines.append(f"  Device {device_id:02d}:        {self.device_requests[device_id]}")

        lines.append(f"")
        lines.append(f"FUNCTION CODE USAGE:")
        for func_code in sorted(self.function_code_counts.keys()):
            func_name = {
                0x01: "Read Coils",
                0x02: "Read Discrete Inputs",
                0x03: "Read Holding Registers",
                0x04: "Read Input Registers",
                0x05: "Write Single Coil",
                0x06: "Write Single Register",
                0x0F: "Write Multiple Coils",
                0x10: "Write Multiple Registers"
            }.get(func_code, f"Unknown (0x{func_code:02X})")
            lines.append(f"  {func_name:25s}: {self.function_code_counts[func_code]}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_recent_errors_summary(self) -> str:
        """Get formatted summary of recent errors"""
        if not self.recent_errors:
            return "No recent errors"

        lines = ["LAST 5 ERRORS (Most Recent First)", "=" * 70, ""]

        for error in reversed(self.recent_errors):
            lines.append(error.format_detailed())
            lines.append("")

        return "\n".join(lines)


class CU48Device:
    """CU48 Lock Controller Device - 48 locks per device"""

    def __init__(self, device_id: int):
        self.device_id = device_id

        # CU48 has 48 locks (addresses 0x00-0x2F)
        # Initialize all locks as CLOSED (True = 1 = locked/closed)
        self.coils = [True] * 48  # All doors start closed/locked

        # Discrete inputs (not used in CU48, but keep for compatibility)
        self.discrete_inputs = [False] * 256

        # Holding registers for CU48 configuration
        self.holding_registers = [0] * 256
        self.input_registers = [0] * 256

        # Uniform CU48 default register values for consistency across devices
        # (Keep room for per-device overrides later if needed.)
        self.holding_registers[0x03] = 550   # Unlock time ms
        self.holding_registers[0x0F] = 0xE230
        self.holding_registers[0xF5] = 0x0002
        self.holding_registers[0xF6] = 0x0004

    def get_lock_status_bytes(self) -> bytes:
        """Get 48 lock statuses as 6 bytes (48 bits)"""
        result = bytearray(6)
        for i in range(48):
            byte_idx = i // 8
            bit_idx = i % 8
            if self.coils[i]:
                result[byte_idx] |= (1 << bit_idx)
        return bytes(result)

    def read_coils(self, start_addr: int, count: int) -> bytes:
        """Read coil status (Function 01) - payload only (no unit/function)"""
        if start_addr >= 48 or start_addr + count > 48:
            return self._exception_response(0x01, 0x02)  # Illegal data address

        byte_count = (count + 7) // 8
        result = bytearray([byte_count])

        for byte_idx in range(byte_count):
            byte_val = 0
            for bit_idx in range(8):
                coil_idx = start_addr + byte_idx * 8 + bit_idx
                if coil_idx < start_addr + count and coil_idx < 48:
                    if self.coils[coil_idx]:
                        byte_val |= (1 << bit_idx)
            result.append(byte_val)

        return bytes(result)

    def read_discrete_inputs(self, start_addr: int, count: int) -> bytes:
        """Read discrete inputs (Function 02) - payload only"""
        if start_addr + count > len(self.discrete_inputs):
            return self._exception_response(0x02, 0x02)

        byte_count = (count + 7) // 8
        result = bytearray([byte_count])

        for byte_idx in range(byte_count):
            byte_val = 0
            for bit_idx in range(8):
                input_idx = start_addr + byte_idx * 8 + bit_idx
                if input_idx < start_addr + count and input_idx < len(self.discrete_inputs):
                    if self.discrete_inputs[input_idx]:
                        byte_val |= (1 << bit_idx)
            result.append(byte_val)

        return bytes(result)

    def read_holding_registers(self, start_addr: int, count: int) -> bytes:
        """Read holding registers (Function 03) - payload only"""
        if start_addr + count > len(self.holding_registers):
            return self._exception_response(0x03, 0x02)

        byte_count = count * 2
        result = bytearray([byte_count])

        for i in range(count):
            reg_val = self.holding_registers[start_addr + i]
            result.extend(struct.pack('>H', reg_val))  # Big-endian

        return bytes(result)

    def read_input_registers(self, start_addr: int, count: int) -> bytes:
        """Read input registers (Function 04) - payload only"""
        if start_addr + count > len(self.input_registers):
            return self._exception_response(0x04, 0x02)

        byte_count = count * 2
        result = bytearray([byte_count])

        for i in range(count):
            reg_val = self.input_registers[start_addr + i]
            result.extend(struct.pack('>H', reg_val))

        return bytes(result)

    def write_single_coil(self, addr: int, value: int) -> Tuple[bytes, Optional[str]]:
        """Write single coil (Function 05) - payload only or exception"""
        if addr >= 48:
            return self._exception_response(0x05, 0x02), None

        operation = None
        if value == 0xFF00:
            self.coils[addr] = True
            operation = f"LOCK #{addr+1} CLOSED"
        elif value == 0x0000:
            self.coils[addr] = False
            operation = f"LOCK #{addr+1} UNLOCKED"
        else:
            return self._exception_response(0x05, 0x03), None  # Illegal data value

        # Echo back the request (payload only)
        return struct.pack('>HH', addr, value), operation

    def write_single_register(self, addr: int, value: int) -> bytes:
        """Write single register (Function 06) - payload only or exception"""
        if addr >= len(self.holding_registers):
            return self._exception_response(0x06, 0x02)

        self.holding_registers[addr] = value & 0xFFFF
        return struct.pack('>HH', addr, value)

    def write_multiple_coils(self, start_addr: int, count: int, values: bytes) -> Tuple[bytes, Optional[str]]:
        """Write multiple coils (Function 0x0F) - payload only or exception"""
        if start_addr >= 48 or start_addr + count > 48:
            return self._exception_response(0x0F, 0x02), None

        operations = []
        for i in range(count):
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < len(values):
                new_state = bool(values[byte_idx] & (1 << bit_idx))
                old_state = self.coils[start_addr + i]
                self.coils[start_addr + i] = new_state

                if new_state != old_state:
                    status = "CLOSED" if new_state else "UNLOCKED"
                    operations.append(f"Lock #{start_addr + i + 1} {status}")

        operation_desc = "; ".join(operations) if operations else None
        return struct.pack('>HH', start_addr, count), operation_desc

    def write_multiple_registers(self, start_addr: int, count: int, values: bytes) -> bytes:
        """Write multiple registers (Function 0x10) - payload only or exception"""
        if start_addr + count > len(self.holding_registers):
            return self._exception_response(0x10, 0x02)

        if len(values) != count * 2:
            return self._exception_response(0x10, 0x03)

        for i in range(count):
            reg_val = struct.unpack('>H', values[i*2:(i+1)*2])[0]
            self.holding_registers[start_addr + i] = reg_val

        return struct.pack('>HH', start_addr, count)

    def _exception_response(self, function_code: int, exception_code: int) -> bytes:
        """Create Modbus exception response payload (function|0x80, exception_code)"""
        return bytes([function_code | 0x80, exception_code])

    def _build_response(self, device_addr: int, function_code: int, data: bytes) -> bytes:
        """Wrap payload or exception payload into a full RTU response"""
        if len(data) == 2 and (data[0] & 0x80):  # Exception payload
            response = bytes([device_addr]) + data
        else:  # Normal payload
            response = bytes([device_addr, function_code]) + data
        response += crc16_bytes(response)
        return response

    def process_request(self, request: bytes) -> Tuple[Optional[bytes], Optional[str]]:
        """Process a Modbus request and return response (full RTU), plus operation text"""
        if len(request) < 4:
            return None, None

        device_addr = request[0]
        if device_addr != self.device_id:
            return None, None  # Not for this device

        function_code = request[1]
        operation = None

        try:
            if function_code == 0x01:  # Read Coils
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_coils(start_addr, count)
                return self._build_response(device_addr, function_code, data), None

            elif function_code == 0x02:  # Read Discrete Inputs
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_discrete_inputs(start_addr, count)
                return self._build_response(device_addr, function_code, data), None

            elif function_code == 0x03:  # Read Holding Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_holding_registers(start_addr, count)
                return self._build_response(device_addr, function_code, data), None

            elif function_code == 0x04:  # Read Input Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_input_registers(start_addr, count)
                return self._build_response(device_addr, function_code, data), None

            elif function_code == 0x05:  # Write Single Coil
                addr = struct.unpack('>H', request[2:4])[0]
                value = struct.unpack('>H', request[4:6])[0]
                data, operation = self.write_single_coil(addr, value)
                return self._build_response(device_addr, function_code, data), operation

            elif function_code == 0x06:  # Write Single Register
                addr = struct.unpack('>H', request[2:4])[0]
                value = struct.unpack('>H', request[4:6])[0]
                data = self.write_single_register(addr, value)
                return self._build_response(device_addr, function_code, data), None

            elif function_code == 0x0F:  # Write Multiple Coils
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                byte_count = request[6]
                values = request[7:7+byte_count]
                data, operation = self.write_multiple_coils(start_addr, count, values)
                return self._build_response(device_addr, function_code, data), operation

            elif function_code == 0x10:  # Write Multiple Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                byte_count = request[6]
                values = request[7:7+byte_count]
                data = self.write_multiple_registers(start_addr, count, values)
                return self._build_response(device_addr, function_code, data), None

            else:
                # Unsupported function code - build exception
                data = self._exception_response(function_code, 0x01)
                return self._build_response(device_addr, function_code, data), None

        except Exception:
            # Generic device failure
            data = self._exception_response(function_code, 0x04)
            return self._build_response(device_addr, function_code, data), None


@dataclass
class CommandLog:
    """Detailed log entry for a received command"""
    timestamp: str
    device_addr: int
    function_code: int
    function_name: str
    raw_request: bytes
    raw_response: bytes
    parameters: str
    result: str

    def format_log(self) -> str:
        """Format command log entry"""
        lines = [
            f"[{self.timestamp}] Device 0x{self.device_addr:02X} - {self.function_name} (0x{self.function_code:02X})"
        ]

        if self.raw_request:
            lines.append(f"  Request:  {self.raw_request.hex(' ').upper()}")

        if self.raw_response:
            lines.append(f"  Response: {self.raw_response.hex(' ').upper()}")

        if self.parameters:
            lines.append(f"  Parameters: {self.parameters}")
        if self.result:
            lines.append(f"  Result: {self.result}")

        lines.append("-" * 70)
        return "\n".join(lines)


class ModbusRTUEmulator:
    """Main Modbus RTU emulator class for CU48 protocol"""

    def __init__(self, num_devices: int):
        self.num_devices = num_devices
        # 1-based addressing: devices 1-10 (addresses 0x01-0x0A)
        self.devices = {i: CU48Device(i) for i in range(1, num_devices + 1)}
        self.stats = Statistics()
        self.serial_port = None
        self.running = False
        self.thread = None
        self.lock_state_callback = None  # Callback for GUI updates
        self.command_log_callback = None  # Callback for command logging

    def set_lock_state_callback(self, callback):
        """Set callback for lock state changes"""
        self.lock_state_callback = callback

    def set_command_log_callback(self, callback):
        """Set callback for command logging"""
        self.command_log_callback = callback

    def start(self, port: str, baudrate: int, timeout: float = 0.1):
        """Start the emulator on specified COM port"""
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout
            )
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            raise Exception(f"Failed to open serial port: {e}")

    def stop(self):
        """Stop the emulator"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

    def _char_time_seconds(self) -> float:
        """Compute one-character time (bits per char ~11)"""
        if not self.serial_port:
            return 0.001
        baud = max(300, int(self.serial_port.baudrate))
        return 11.0 / baud

    def _frame_gap_seconds(self) -> float:
        """3.5 character times gap"""
        return max(0.0015, 3.5 * self._char_time_seconds())

    def _receive_loop(self):
        """Main receive loop for processing Modbus requests"""
        buffer = bytearray()
        last_receive_time = time.time()

        while self.running:
            try:
                # Check for incoming data
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        buffer.extend(data)
                        last_receive_time = time.time()
                        self.stats.bytes_received += len(data)
                else:
                    # If there's data waiting and gap exceeded, try to extract frames
                    if len(buffer) > 0 and (time.time() - last_receive_time) > self._frame_gap_seconds():
                        self._extract_and_process_frames(buffer)
                        # _extract_and_process_frames mutates the buffer in place

                    time.sleep(0.001)  # Small delay

            except Exception as e:
                print(f"Error in receive loop: {e}")
                time.sleep(0.1)

    def _extract_and_process_frames(self, buf: bytearray):
        """
        Extract one or more valid Modbus RTU frames from the buffer.
        Strategy: sliding window looking for earliest valid CRC. This prevents
        merged-frame CRC errors when back-to-back requests arrive quickly.
        """
        # Safety bound: don't let buffer grow without limit
        MAX_BUF = 4096
        if len(buf) > MAX_BUF:
            # If buffer is huge and no frames found, clear with a framing error
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.stats.framing_errors += 1
            self.stats.invalid_requests += 1
            error = ErrorDetail(
                timestamp=timestamp,
                error_type="FRAMING",
                frame=bytes(buf),
                description=f"Buffer overflow without CRC match (> {MAX_BUF} bytes)",
                error_position=None
            )
            self.stats.add_error(error)
            buf.clear()
            return

        # Try to peel off frames one by one
        while len(buf) >= 4:
            # Find the earliest CRC-valid slice
            found = False
            for i in range(4, len(buf) + 1):
                if verify_crc(buf[:i]):
                    # Process this frame
                    frame = bytes(buf[:i])
                    # Remove it from buffer
                    del buf[:i]
                    self._process_frame(frame)
                    found = True
                    break

            if not found:
                # No valid frame prefix found yet; keep the buffer for more data
                break

    def _process_frame(self, frame: bytes):
        """Process a received Modbus frame"""
        self.stats.total_requests += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # LOG ALL RECEIVED FRAMES (even invalid ones)
        self._log_raw_frame(frame, timestamp)

        # Minimum Modbus frame check
        if len(frame) < 4:
            self.stats.framing_errors += 1
            self.stats.invalid_requests += 1
            error = ErrorDetail(
                timestamp=timestamp,
                error_type="FRAMING",
                frame=frame,
                description=f"Frame too short: {len(frame)} bytes (minimum 4 bytes required)",
                error_position=None
            )
            self.stats.add_error(error)
            return

        # Verify CRC
        if not verify_crc(frame):
            self.stats.crc_errors += 1
            self.stats.invalid_requests += 1

            data = frame[:-2]
            expected_crc = crc16_bytes(data)
            received_crc = frame[-2:]

            error = ErrorDetail(
                timestamp=timestamp,
                error_type="CRC",
                frame=frame,
                description=f"CRC mismatch: received {received_crc.hex().upper()}, expected {expected_crc.hex().upper()}",
                expected_value=expected_crc,
                error_position=len(frame) - 2
            )
            self.stats.add_error(error)
            return

        # Extract device address and function code
        device_addr = frame[0]
        function_code = frame[1]

        # Update statistics
        self.stats.valid_requests += 1
        self.stats.device_requests[device_addr] = self.stats.device_requests.get(device_addr, 0) + 1
        self.stats.function_code_counts[function_code & 0x7F] = self.stats.function_code_counts.get(function_code & 0x7F, 0) + 1

        # Check if this device is emulated
        if device_addr not in self.devices:
            # Not our device, ignore (no response on Modbus RTU)
            self._log_raw_response(None, "No response - device not emulated", timestamp)
            return

        # Process request and generate response
        device = self.devices[device_addr]
        response, operation = device.process_request(frame[:-2])  # Remove CRC before processing

        if response:
            # Log the response
            self._log_raw_response(response, f"Response sent ({len(response)} bytes)", timestamp)

            # Log the command (detailed decode)
            self._log_command(frame, response, function_code & 0x7F, device_addr, operation, timestamp)

            # Check if function code is supported / exception response
            if response[1] & 0x80:  # Exception response in RTU frame
                if len(response) > 2 and response[2] == 0x01:  # Illegal function
                    self.stats.unsupported_function += 1
                    error = ErrorDetail(
                        timestamp=timestamp,
                        error_type="UNSUPPORTED",
                        frame=frame,
                        description=f"Unsupported function code: 0x{function_code:02X}",
                        error_position=1
                    )
                    self.stats.add_error(error)

            # Update lock operation statistics
            if operation:
                if "UNLOCKED" in operation:
                    self.stats.locks_unlocked += operation.count("UNLOCKED")
                if "CLOSED" in operation:
                    self.stats.locks_locked += operation.count("CLOSED")

                # Notify GUI of lock state change
                if self.lock_state_callback:
                    self.lock_state_callback(device_addr, operation)

            # Send response (half-duplex: wait a bit before responding)
            time.sleep(0.002)  # 2ms response delay
            if self.serial_port:
                self.serial_port.write(response)
            self.stats.bytes_sent += len(response)
            self.stats.responses_sent += 1

    def _log_raw_frame(self, frame: bytes, timestamp: str):
        """Log raw received frame to command log"""
        if not self.command_log_callback:
            return

        device_addr = frame[0] if len(frame) > 0 else 0
        function_code = frame[1] if len(frame) > 1 else 0

        function_names = {
            0x01: "Read Coils",
            0x02: "Read Discrete Inputs",
            0x03: "Read Holding Registers",
            0x04: "Read Input Registers",
            0x05: "Write Single Coil",
            0x06: "Write Single Register",
            0x0F: "Write Multiple Coils",
            0x10: "Write Multiple Registers"
        }
        function_name = function_names.get(function_code & 0x7F, f"Unknown (0x{function_code:02X})")

        crc_valid = verify_crc(frame) if len(frame) >= 4 else False
        crc_status = "✓ Valid" if crc_valid else "✗ Invalid"

        log_entry = CommandLog(
            timestamp=timestamp,
            device_addr=device_addr,
            function_code=function_code & 0x7F,
            function_name=function_name,
            raw_request=frame,
            raw_response=b'',
            parameters=f"Frame length: {len(frame)} bytes, CRC: {crc_status}",
            result="Received (processing...)"
        )

        self.command_log_callback(log_entry)

    def _log_raw_response(self, response: Optional[bytes], description: str, timestamp: str):
        """Log raw response sent"""
        if not self.command_log_callback:
            return

        if response:
            log_entry = CommandLog(
                timestamp=timestamp,
                device_addr=response[0] if len(response) > 0 else 0,
                function_code=(response[1] & 0x7F) if len(response) > 1 else 0,
                function_name="Response",
                raw_request=b'',
                raw_response=response,
                parameters=description,
                result=f"Sent {len(response)} bytes"
            )
        else:
            log_entry = CommandLog(
                timestamp=timestamp,
                device_addr=0,
                function_code=0,
                function_name="No Response",
                raw_request=b'',
                raw_response=b'',
                parameters=description,
                result="No response sent"
            )

        self.command_log_callback(log_entry)

    def _log_command(self, request: bytes, response: bytes, function_code: int, device_addr: int, operation: Optional[str], timestamp: str):
        """Log a command with detailed decoding"""
        if not self.command_log_callback:
            return

        function_names = {
            0x01: "Read Coils",
            0x02: "Read Discrete Inputs",
            0x03: "Read Holding Registers",
            0x04: "Read Input Registers",
            0x05: "Write Single Coil",
            0x06: "Write Single Register",
            0x0F: "Write Multiple Coils",
            0x10: "Write Multiple Registers"
        }
        function_name = function_names.get(function_code, f"Unknown (0x{function_code:02X})")

        parameters = ""
        result = ""

        try:
            if function_code in [0x01, 0x02]:  # Read Coils/Inputs
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                parameters = f"Start: 0x{start_addr:04X} ({start_addr}), Count: {count}"
                if len(response) > 3 and not (response[1] & 0x80):
                    byte_count = response[2]
                    data_bytes = response[3:3+byte_count]
                    result = f"Returned {byte_count} bytes: {data_bytes.hex(' ').upper()}"
                else:
                    result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 else "Exception"

            elif function_code in [0x03, 0x04]:  # Read Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                parameters = f"Start: 0x{start_addr:04X} ({start_addr}), Count: {count}"
                if len(response) > 3 and not (response[1] & 0x80):
                    byte_count = response[2]
                    result = f"Returned {byte_count // 2} registers ({byte_count} bytes)"
                else:
                    result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 else "Exception"

            elif function_code == 0x05:  # Write Single Coil
                addr = struct.unpack('>H', request[2:4])[0]
                value = struct.unpack('>H', request[4:6])[0]
                coil_state = "ON (Close/Lock)" if value == 0xFF00 else "OFF (Unlock)" if value == 0x0000 else f"Invalid (0x{value:04X})"
                parameters = f"Lock #{addr + 1} (0x{addr:04X}), Value: {coil_state}"
                if operation:
                    result = operation
                else:
                    result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else "Success"

            elif function_code == 0x06:  # Write Single Register
                addr = struct.unpack('>H', request[2:4])[0]
                value = struct.unpack('>H', request[4:6])[0]
                parameters = f"Register: 0x{addr:04X} ({addr}), Value: 0x{value:04X} ({value})"
                result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else "Success"

            elif function_code == 0x0F:  # Write Multiple Coils
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                byte_count = request[6]
                values = request[7:7+byte_count]
                parameters = f"Start: 0x{start_addr:04X} (Lock #{start_addr + 1}), Count: {count}, Data: {values.hex(' ').upper()}"
                if operation:
                    result = operation
                else:
                    result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else f"Written {count} coils"

            elif function_code == 0x10:  # Write Multiple Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                byte_count = request[6]
                parameters = f"Start: 0x{start_addr:04X} ({start_addr}), Count: {count}, Bytes: {byte_count}"
                result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else f"Written {count} registers"

            else:
                parameters = "Unsupported function"
                result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 else "Error"

        except Exception as e:
            parameters = f"Error decoding: {e}"
            result = "Parse error"

        log_entry = CommandLog(
            timestamp=timestamp,
            device_addr=device_addr,
            function_code=function_code,
            function_name=function_name,
            raw_request=request,
            raw_response=response,
            parameters=parameters,
            result=result
        )
        self.command_log_callback(log_entry)


class EmulatorGUI:
    """Windows GUI for Modbus RTU Emulator V3 (CU48)"""

    def __init__(self, root):
        self.root = root
        self.root.title("Modbus RTU Slave Emulator V3 - CU48 Protocol (Fixed)")
        self.root.geometry("1200x900")

        self.emulator = None
        self.log_update_timer = None
        self.lock_buttons = {}  # Store lock button widgets

        self._create_widgets()
        self._refresh_ports()

    def _create_widgets(self):
        """Create GUI widgets"""
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        # COM Port
        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(config_frame, textvariable=self.port_var, width=15, state='readonly')
        self.port_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        refresh_btn = ttk.Button(config_frame, text="Refresh", command=self._refresh_ports)
        refresh_btn.grid(row=0, column=2, padx=5, pady=5)

        # Baud Rate
        ttk.Label(config_frame, text="Baud Rate:").grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.baudrate_var = tk.StringVar(value="115200")  # CU48 default
        baudrate_combo = ttk.Combobox(config_frame, textvariable=self.baudrate_var,
                                      values=["9600", "19200", "38400", "57600", "115200"],
                                      width=10, state='readonly')
        baudrate_combo.grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)

        # Number of Devices
        ttk.Label(config_frame, text="Num Devices:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.num_devices_var = tk.IntVar(value=1)
        devices_spin = ttk.Spinbox(config_frame, from_=1, to=10, textvariable=self.num_devices_var, width=10)
        devices_spin.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Control Buttons
        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=1, column=3, columnspan=2, padx=5, pady=5)

        self.start_btn = ttk.Button(button_frame, text="Start Emulator", command=self._start_emulator)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(button_frame, text="Stop Emulator", command=self._stop_emulator, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Status Frame
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="Status: Stopped", foreground="red")
        self.status_label.pack()

        # Main content area with notebook
        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        notebook = ttk.Notebook(content_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Lock Control Tab
        lock_control_frame = ttk.Frame(notebook)
        notebook.add(lock_control_frame, text="Lock Control (CU48)")

        # Device selector
        device_select_frame = ttk.Frame(lock_control_frame)
        device_select_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(device_select_frame, text="Device:").pack(side=tk.LEFT, padx=5)
        self.selected_device_var = tk.IntVar(value=1)
        self.device_selector = ttk.Spinbox(device_select_frame, from_=1, to=10,
                                           textvariable=self.selected_device_var, width=5,
                                           command=self._update_lock_display)
        self.device_selector.pack(side=tk.LEFT, padx=5)

        ttk.Label(device_select_frame, text="(48 locks per device)").pack(side=tk.LEFT, padx=5)

        # Scrollable frame for locks
        lock_canvas = tk.Canvas(lock_control_frame)
        lock_scrollbar = ttk.Scrollbar(lock_control_frame, orient="vertical", command=lock_canvas.yview)
        self.lock_grid_frame = ttk.Frame(lock_canvas)

        lock_canvas.configure(yscrollcommand=lock_scrollbar.set)
        lock_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lock_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lock_canvas.create_window((0, 0), window=self.lock_grid_frame, anchor="nw")

        self.lock_grid_frame.bind("<Configure>", lambda e: lock_canvas.configure(scrollregion=lock_canvas.bbox("all")))

        # Create 48 lock indicators/controls (8 columns x 6 rows)
        self._create_lock_controls()

        # Statistics tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")

        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=20, width=90,
                                                     font=("Courier New", 9))
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Error details tab
        error_frame = ttk.Frame(notebook)
        notebook.add(error_frame, text="Last 5 Errors")

        self.error_text = scrolledtext.ScrolledText(error_frame, height=20, width=90,
                                                     font=("Courier New", 8),
                                                     foreground="red")
        self.error_text.pack(fill=tk.BOTH, expand=True)

        # Command Log tab
        command_log_frame = ttk.Frame(notebook)
        notebook.add(command_log_frame, text="Command Log")

        self.command_log_text = scrolledtext.ScrolledText(command_log_frame, height=20, width=90,
                                                          font=("Courier New", 8),
                                                          foreground="blue")
        self.command_log_text.pack(fill=tk.BOTH, expand=True)

        # Communication log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="System Log")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=90,
                                                   font=("Courier New", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(action_frame, text="Clear System Log", command=self._clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Clear Command Log", command=self._clear_command_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Clear Errors", command=self._clear_errors).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Save Statistics", command=self._save_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Save Command Log", command=self._save_command_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Reset Statistics", command=self._reset_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Close All Locks", command=self._close_all_locks).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Unlock All Locks", command=self._unlock_all_locks).pack(side=tk.LEFT, padx=5)

    def _create_lock_controls(self):
        """Create 48 lock indicator buttons"""
        info_label = ttk.Label(self.lock_grid_frame, text="48 CU48 Locks - Green=Closed/Locked (1), Red=Unlocked (0)")
        info_label.grid(row=0, column=0, columnspan=8, pady=5)

        for i in range(48):
            row = (i // 8) + 1
            col = i % 8

            frame = ttk.Frame(self.lock_grid_frame, relief=tk.RAISED, borderwidth=1)
            frame.grid(row=row, column=col, padx=2, pady=2, sticky=tk.NSEW)

            label = ttk.Label(frame, text=f"Lock {i+1}")
            label.pack()

            button = tk.Button(frame, text="CLOSED", bg="green", fg="white",
                             command=lambda lock_idx=i: self._toggle_lock(lock_idx))
            button.pack(fill=tk.BOTH, expand=True)

            self.lock_buttons[i] = button

    def _update_lock_display(self):
        """Update lock display for selected device"""
        if not self.emulator:
            return

        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices:
            return

        device = self.emulator.devices[device_id]

        for i in range(48):
            if device.coils[i]:  # True = closed/locked
                self.lock_buttons[i].config(text="CLOSED", bg="green")
            else:  # False = unlocked
                self.lock_buttons[i].config(text="UNLOCKED", bg="red")

    def _toggle_lock(self, lock_idx: int):
        """Toggle a single lock state"""
        if not self.emulator:
            messagebox.showwarning("Warning", "Emulator not running")
            return

        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices:
            messagebox.showerror("Error", f"Device {device_id} not emulated")
            return

        device = self.emulator.devices[device_id]
        device.coils[lock_idx] = not device.coils[lock_idx]
        self._update_lock_display()

        status = "CLOSED/LOCKED" if device.coils[lock_idx] else "UNLOCKED"
        self._log(f"Device {device_id} Lock #{lock_idx+1} manually set to {status}")

    def _close_all_locks(self):
        """Close/lock all locks on selected device"""
        if not self.emulator:
            messagebox.showwarning("Warning", "Emulator not running")
            return

        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices:
            return

        device = self.emulator.devices[device_id]
        device.coils = [True] * 48
        self._update_lock_display()
        self._log(f"Device {device_id}: All locks CLOSED/LOCKED")

    def _unlock_all_locks(self):
        """Unlock all locks on selected device"""
        if not self.emulator:
            messagebox.showwarning("Warning", "Emulator not running")
            return

        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices:
            return

        device = self.emulator.devices[device_id]
        device.coils = [False] * 48
        self._update_lock_display()
        self._log(f"Device {device_id}: All locks UNLOCKED")

    def _on_lock_state_change(self, device_id: int, operation: str):
        """Callback when lock state changes via Modbus"""
        self._log(f"Device {device_id}: {operation}")
        if device_id == self.selected_device_var.get():
            self.root.after(100, self._update_lock_display)

    def _on_command_received(self, command_log: 'CommandLog'):
        """Callback when a command is received and logged"""
        log_text = command_log.format_log()
        self.command_log_text.insert(tk.END, log_text + "\n")
        self.command_log_text.see(tk.END)

        if "UNLOCK" in command_log.result or "CLOSED" in command_log.result:
            self._log(f"CMD: Device {command_log.device_addr} - {command_log.result}")

    def _refresh_ports(self):
        """Refresh available COM ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def _start_emulator(self):
        """Start the Modbus emulator"""
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return

        baudrate = int(self.baudrate_var.get())
        num_devices = self.num_devices_var.get()

        try:
            self.emulator = ModbusRTUEmulator(num_devices)
            self.emulator.set_lock_state_callback(self._on_lock_state_change)
            self.emulator.set_command_log_callback(self._on_command_received)
            self.emulator.start(port, baudrate)

            self.status_label.config(text=f"Status: Running on {port} @ {baudrate} baud, {num_devices} CU48 device(s)",
                                    foreground="green")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)

            self._log(f"CU48 Emulator V3 (Fixed) started: {port} @ {baudrate} baud")
            self._log(f"Emulating CU48 devices: {', '.join([str(i) for i in range(1, num_devices + 1)])}")
            self._log(f"Each device has 48 locks (all initially CLOSED/LOCKED)")
            self._log(f"Command logging enabled - all commands will be logged to 'Command Log' tab")

            self._update_lock_display()
            self._update_statistics()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _stop_emulator(self):
        """Stop the Modbus emulator"""
        if self.emulator:
            self.emulator.stop()

            final_stats = self.emulator.stats.get_summary()
            self._log("\n" + final_stats)

            self.emulator = None

        self.status_label.config(text="Status: Stopped", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        if self.log_update_timer:
            self.root.after_cancel(self.log_update_timer)

    def _update_statistics(self):
        """Update statistics display"""
        if self.emulator and self.emulator.running:
            stats_summary = self.emulator.stats.get_summary()
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_summary)

            errors_summary = self.emulator.stats.get_recent_errors_summary()
            self.error_text.delete(1.0, tk.END)
            self.error_text.insert(1.0, errors_summary)

            self._update_lock_display()
            self.log_update_timer = self.root.after(1000, self._update_statistics)

    def _log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

    def _clear_log(self):
        """Clear the system log"""
        self.log_text.delete(1.0, tk.END)

    def _clear_command_log(self):
        """Clear the command log"""
        self.command_log_text.delete(1.0, tk.END)
        self._log("Command log cleared")

    def _clear_errors(self):
        """Clear the error display"""
        if self.emulator:
            self.emulator.stats.recent_errors.clear()
            self.error_text.delete(1.0, tk.END)
            self.error_text.insert(1.0, "No recent errors")
            self._log("Error list cleared")

    def _save_statistics(self):
        """Save statistics to file"""
        if not self.emulator:
            messagebox.showwarning("Warning", "No emulator running")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"modbus_cu48_stats_{timestamp}.txt"

        try:
            with open(filename, 'w') as f:
                f.write(self.emulator.stats.get_summary())
                f.write("\n\n")
                f.write(self.emulator.stats.get_recent_errors_summary())

            messagebox.showinfo("Success", f"Statistics saved to {filename}")
            self._log(f"Statistics saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save statistics: {e}")

    def _save_command_log(self):
        """Save command log to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"modbus_cu48_commands_{timestamp}.log"

        try:
            log_content = self.command_log_text.get(1.0, tk.END)

            if not log_content.strip():
                messagebox.showwarning("Warning", "Command log is empty")
                return

            with open(filename, 'w') as f:
                f.write("=" * 70 + "\n")
                f.write("MODBUS RTU CU48 EMULATOR - COMMAND LOG\n")
                f.write("=" * 70 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 70 + "\n\n")
                f.write(log_content)

            messagebox.showinfo("Success", f"Command log saved to {filename}")
            self._log(f"Command log saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save command log: {e}")

    def _reset_statistics(self):
        """Reset statistics"""
        if self.emulator:
            self.emulator.stats.reset()
            self._log("Statistics reset")

    def on_closing(self):
        """Handle window closing"""
        if self.emulator and self.emulator.running:
            self._stop_emulator()
        self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = EmulatorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
