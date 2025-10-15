#!/usr/bin/env python3
"""
Modbus RTU Slave Emulator for Windows - Version 3 (CU48 Protocol)
Variant: Fixed+ (Lockstate)
- Robust frame splitting, CRC, and consistent response wrapping.
- Spec-strict handling for count==0 (exception 0x03), with optional CU48 compat: count==0 -> read 48.
- Maintains a 48-bit status register per device (starts all 1s = CLOSED).
- Read Coils (0x01) replies from the status register.
- Write Single Coil (0x05): 0xFF00 -> OPEN (bit->0), 0x0000 -> CLOSE (bit->1).
- Write Multiple Coils (0x0F): incoming bit 1=CLOSE, 0=OPEN; updates status register.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional
from collections import deque
import struct

# ------------- CRC helpers -------------

def calculate_crc16(data: bytes) -> int:
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
    return struct.pack('<H', calculate_crc16(data))

def verify_crc(message: bytes) -> bool:
    if len(message) < 4:
        return False
    return message[-2:] == crc16_bytes(message[:-2])


# ------------- Data classes -------------

@dataclass
class ErrorDetail:
    timestamp: str
    error_type: str
    frame: bytes
    description: str
    expected_value: Optional[bytes] = None
    error_position: Optional[int] = None

    def format_detailed(self) -> str:
        lines = [
            f"[{self.timestamp}] {self.error_type} ERROR",
            f"Description: {self.description}",
            "",
            f"Received Frame ({len(self.frame)} bytes):"
        ]
        hex_line = "  "; pos_line = "  "
        for i, byte in enumerate(self.frame):
            if self.error_position is not None and i == self.error_position:
                hex_line += f"[{byte:02X}] "; pos_line += " ^^  "
            else:
                hex_line += f" {byte:02X}  "; pos_line += "     "
        lines.append(hex_line)
        if self.error_position is not None:
            lines.append(pos_line); lines.append(f"  Error at byte position {self.error_position}")
        lines.append("=" * 70)
        return "\n".join(lines)


@dataclass
class Statistics:
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

    device_requests: Dict[int, int] = field(default_factory=dict)
    function_code_counts: Dict[int, int] = field(default_factory=dict)
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=5))

    locks_unlocked: int = 0
    locks_locked: int = 0

    def add_error(self, error: 'ErrorDetail'):
        self.recent_errors.append(error)

    def reset(self):
        self.__init__()

    def get_summary(self) -> str:
        elapsed = time.time() - self.start_time
        lines = [
            "=" * 60,
            "MODBUS RTU SLAVE EMULATOR V3 - STATISTICS (CU48)",
            "=" * 60,
            f"Runtime: {elapsed:.1f} seconds",
            "",
            "REQUESTS:",
            f"  Total Requests:     {self.total_requests}",
            f"  Valid Requests:     {self.valid_requests}",
            f"  Invalid Requests:   {self.invalid_requests}",
            f"  Responses Sent:     {self.responses_sent}",
            "",
            "ERRORS:",
            f"  CRC Errors:         {self.crc_errors}",
            f"  Framing Errors:     {self.framing_errors}",
            f"  Timeout Errors:     {self.timeout_errors}",
            f"  Unsupported Func:   {self.unsupported_function}",
            "",
            "CU48 LOCK OPERATIONS:",
            f"  Locks Unlocked:     {self.locks_unlocked}",
            f"  Locks Locked:       {self.locks_locked}",
            "",
            "DATA TRANSFER:",
            f"  Bytes Received:     {self.bytes_received}",
            f"  Bytes Sent:         {self.bytes_sent}",
            "",
            "PER-DEVICE REQUESTS:"
        ]
        for device_id in sorted(self.device_requests.keys()):
            lines.append(f"  Device {device_id:02d}:        {self.device_requests[device_id]}")
        lines.append("")
        lines.append("FUNCTION CODE USAGE:")
        for func_code in sorted(self.function_code_counts.keys()):
            func_name = {
                0x01: "Read Coils", 0x02: "Read Discrete Inputs",
                0x03: "Read Holding Registers", 0x04: "Read Input Registers",
                0x05: "Write Single Coil", 0x06: "Write Single Register",
                0x0F: "Write Multiple Coils", 0x10: "Write Multiple Registers"
            }.get(func_code, f"Unknown (0x{func_code:02X})")
            lines.append(f"  {func_name:25s}: {self.function_code_counts[func_code]}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def get_recent_errors_summary(self) -> str:
        if not self.recent_errors:
            return "No recent errors"
        lines = ["LAST 5 ERRORS (Most Recent First)", "=" * 70, ""]
        for error in reversed(self.recent_errors):
            lines.append(error.format_detailed())
            lines.append("")
        return "\n".join(lines)


# ------------- CU48 Device (Lockstate) -------------

class CU48Device:
    def __init__(self, device_id: int, cu48_zero_means_all: bool = False):
        self.device_id = device_id
        self.cu48_zero_means_all = cu48_zero_means_all

        # Logical coils view: True=CLOSED/LOCKED, False=OPEN
        self.coils = [True] * 48

        # Internal 48-bit status register, 6 bytes; bit=1 CLOSED, bit=0 OPEN
        self.status_reg = bytearray([0xFF] * 6)

        # Other maps
        self.discrete_inputs = [False] * 256
        self.holding_registers = [0] * 256
        self.input_registers = [0] * 256
        # Uniform defaults
        self.holding_registers[0x03] = 550
        self.holding_registers[0x0F] = 0xE230
        self.holding_registers[0xF5] = 0x0002
        self.holding_registers[0xF6] = 0x0004

    # ---- helpers ----
    def _set_bit(self, idx: int, closed: bool):
        b = idx // 8; bit = idx % 8
        if closed:
            self.status_reg[b] |= (1 << bit)
        else:
            self.status_reg[b] &= ~(1 << bit)

    def _sync_status_from_coils(self):
        for i, c in enumerate(self.coils):
            self._set_bit(i, closed=c)

    # ---- function code handlers ----
    def read_coils(self, start_addr: int, count: int) -> bytes:
        # Strict: count==0 invalid unless CU48 toggled
        if count == 0:
            if self.cu48_zero_means_all:
                count = 48 - start_addr if start_addr < 48 else 0
            else:
                return bytes([0x01 | 0x80, 0x03])  # illegal data value
        if start_addr >= 48 or start_addr + count > 48:
            return bytes([0x01 | 0x80, 0x02])  # illegal address

        # Ensure register reflects current coils
        self._sync_status_from_coils()

        byte_count = (count + 7) // 8
        out = bytearray([byte_count])
        for b in range(byte_count):
            v = 0
            for bit in range(8):
                idx = start_addr + b*8 + bit
                if idx < start_addr + count and idx < 48:
                    vb = (self.status_reg[idx // 8] >> (idx % 8)) & 1
                    v |= (vb << bit)
            out.append(v)
        return bytes(out)

    def read_discrete_inputs(self, start_addr: int, count: int) -> bytes:
        if count == 0:
            return bytes([0x02 | 0x80, 0x03])
        if start_addr + count > len(self.discrete_inputs):
            return bytes([0x02 | 0x80, 0x02])
        byte_count = (count + 7) // 8
        res = bytearray([byte_count])
        for b in range(byte_count):
            v = 0
            for bit in range(8):
                idx = start_addr + b*8 + bit
                if idx < start_addr + count and self.discrete_inputs[idx]:
                    v |= (1 << bit)
            res.append(v)
        return bytes(res)

    def read_holding_registers(self, start_addr: int, count: int) -> bytes:
        if count == 0:
            return bytes([0x03 | 0x80, 0x03])
        if start_addr + count > len(self.holding_registers):
            return bytes([0x03 | 0x80, 0x02])
        res = bytearray([count * 2])
        for i in range(count):
            res.extend(struct.pack('>H', self.holding_registers[start_addr + i]))
        return bytes(res)

    def read_input_registers(self, start_addr: int, count: int) -> bytes:
        if count == 0:
            return bytes([0x04 | 0x80, 0x03])
        if start_addr + count > len(self.input_registers):
            return bytes([0x04 | 0x80, 0x02])
        res = bytearray([count * 2])
        for i in range(count):
            res.extend(struct.pack('>H', self.input_registers[start_addr + i]))
        return bytes(res)

    def write_single_coil(self, addr: int, value: int) -> Tuple[bytes, Optional[str]]:
        if addr >= 48:
            return (bytes([0x05 | 0x80, 0x02]), None)
        # New semantics per request: FF00=OPEN (bit->0); 0000=CLOSE (bit->1)
        if value == 0xFF00:
            self.coils[addr] = False
            self._set_bit(addr, closed=False)
            op = f"LOCK #{addr+1} OPENED/UNLOCKED"
        elif value == 0x0000:
            self.coils[addr] = True
            self._set_bit(addr, closed=True)
            op = f"LOCK #{addr+1} CLOSED/LOCKED"
        else:
            return (bytes([0x05 | 0x80, 0x03]), None)
        return (struct.pack('>HH', addr, value), op)

    def write_multiple_coils(self, start_addr: int, count: int, values: bytes) -> Tuple[bytes, Optional[str]]:
        if count == 0:
            return (bytes([0x0F | 0x80, 0x03]), None)
        if start_addr >= 48 or start_addr + count > 48:
            return (bytes([0x0F | 0x80, 0x02]), None)
        ops = []
        for i in range(count):
            b = i // 8; bit = i % 8
            if b < len(values):
                incoming_closed = bool(values[b] & (1 << bit))  # 1=CLOSE, 0=OPEN
                idx = start_addr + i
                self.coils[idx] = incoming_closed
                self._set_bit(idx, closed=incoming_closed)
                ops.append(f"Lock #{idx+1} {'CLOSED/LOCKED' if incoming_closed else 'OPENED/UNLOCKED'}")
        return (struct.pack('>HH', start_addr, count), "; ".join(ops) if ops else None)

    def write_single_register(self, addr: int, value: int) -> bytes:
        if addr >= len(self.holding_registers):
            return bytes([0x06 | 0x80, 0x02])
        self.holding_registers[addr] = value & 0xFFFF
        return struct.pack('>HH', addr, value)

    def write_multiple_registers(self, start_addr: int, count: int, values: bytes) -> bytes:
        if count == 0:
            return bytes([0x10 | 0x80, 0x03])
        if start_addr + count > len(self.holding_registers):
            return bytes([0x10 | 0x80, 0x02])
        if len(values) != count * 2:
            return bytes([0x10 | 0x80, 0x03])
        for i in range(count):
            self.holding_registers[start_addr + i] = struct.unpack('>H', values[i*2:(i+1)*2])[0]
        return struct.pack('>HH', start_addr, count)

    def _build_response(self, device_addr: int, function_code: int, data: bytes) -> bytes:
        if len(data) == 2 and (data[0] & 0x80):
            resp = bytes([device_addr]) + data
        else:
            resp = bytes([device_addr, function_code]) + data
        return resp + crc16_bytes(resp)

    def process_request(self, request: bytes) -> Tuple[Optional[bytes], Optional[str]]:
        if len(request) < 4:
            return None, None
        device_addr = request[0]
        if device_addr != self.device_id:
            return None, None
        fc = request[1]
        try:
            if fc == 0x01:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                return (self._build_response(device_addr, fc, self.read_coils(sa, cnt)), None)
            if fc == 0x02:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                return (self._build_response(device_addr, fc, self.read_discrete_inputs(sa, cnt)), None)
            if fc == 0x03:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                return (self._build_response(device_addr, fc, self.read_holding_registers(sa, cnt)), None)
            if fc == 0x04:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                return (self._build_response(device_addr, fc, self.read_input_registers(sa, cnt)), None)
            if fc == 0x05:
                a = struct.unpack('>H', request[2:4])[0]
                v = struct.unpack('>H', request[4:6])[0]
                payload, op = self.write_single_coil(a, v)
                return (self._build_response(device_addr, fc, payload), op)
            if fc == 0x06:
                a = struct.unpack('>H', request[2:4])[0]
                v = struct.unpack('>H', request[4:6])[0]
                return (self._build_response(device_addr, fc, self.write_single_register(a, v)), None)
            if fc == 0x0F:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                bc = request[6]
                vals = request[7:7+bc]
                payload, op = self.write_multiple_coils(sa, cnt, vals)
                return (self._build_response(device_addr, fc, payload), op)
            if fc == 0x10:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                bc = request[6]
                vals = request[7:7+bc]
                return (self._build_response(device_addr, fc, self.write_multiple_registers(sa, cnt, vals)), None)
            payload = bytes([fc | 0x80, 0x01])
            return (self._build_response(device_addr, fc, payload), None)
        except Exception:
            payload = bytes([fc | 0x80, 0x04])
            return (self._build_response(device_addr, fc, payload), None)


# ------------- Emulator core -------------

class ModbusRTUEmulator:
    def __init__(self, num_devices: int, cu48_zero_means_all: bool = False):
        self.num_devices = num_devices
        self.cu48_zero_means_all = cu48_zero_means_all
        self.devices = {i: CU48Device(i, cu48_zero_means_all) for i in range(1, num_devices + 1)}
        self.stats = Statistics()
        self.serial_port = None
        self.running = False
        self.thread = None
        self.lock_state_callback = None
        self.command_log_callback = None

    def set_lock_state_callback(self, callback):
        self.lock_state_callback = callback

    def set_command_log_callback(self, callback):
        self.command_log_callback = callback

    def start(self, port: str, baudrate: int, timeout: float = 0.1):
        try:
            self.serial_port = serial.Serial(
                port=port, baudrate=baudrate, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=timeout
            )
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            raise Exception(f"Failed to open serial port: {e}")

    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=2)
        if self.serial_port and self.serial_port.is_open: self.serial_port.close()

    def _char_time_seconds(self) -> float:
        baud = max(300, int(self.serial_port.baudrate) if self.serial_port else 115200)
        return 11.0 / baud

    def _frame_gap_seconds(self) -> float:
        return max(0.0015, 3.5 * self._char_time_seconds())

    def _receive_loop(self):
        buffer = bytearray()
        last_receive_time = time.time()
        while self.running:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        buffer.extend(data); last_receive_time = time.time()
                        self.stats.bytes_received += len(data)
                else:
                    if len(buffer) > 0 and (time.time() - last_receive_time) > self._frame_gap_seconds():
                        self._extract_and_process_frames(buffer)
                    time.sleep(0.001)
            except Exception as e:
                print(f"Error in receive loop: {e}"); time.sleep(0.1)

    def _extract_and_process_frames(self, buf: bytearray):
        MAX_BUF = 4096
        if len(buf) > MAX_BUF:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.stats.framing_errors += 1; self.stats.invalid_requests += 1
            self.stats.add_error(ErrorDetail(ts, "FRAMING", bytes(buf), f"Buffer overflow (> {MAX_BUF} bytes)"))
            buf.clear(); return
        while len(buf) >= 4:
            found = False
            for i in range(4, len(buf) + 1):
                if verify_crc(buf[:i]):
                    frame = bytes(buf[:i]); del buf[:i]
                    self._process_frame(frame); found = True; break
            if not found: break

    def _process_frame(self, frame: bytes):
        self.stats.total_requests += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._log_raw_frame(frame, timestamp)

        if len(frame) < 4:
            self.stats.framing_errors += 1; self.stats.invalid_requests += 1
            self.stats.add_error(ErrorDetail(timestamp, "FRAMING", frame, f"Frame too short: {len(frame)} bytes"))
            return
        if not verify_crc(frame):
            self.stats.crc_errors += 1; self.stats.invalid_requests += 1
            exp = crc16_bytes(frame[:-2])
            self.stats.add_error(ErrorDetail(timestamp, "CRC", frame, f"CRC mismatch", exp, len(frame)-2))
            return

        device_addr = frame[0]; function_code = frame[1]
        self.stats.valid_requests += 1
        self.stats.device_requests[device_addr] = self.stats.device_requests.get(device_addr, 0) + 1
        self.stats.function_code_counts[function_code & 0x7F] = self.stats.function_code_counts.get(function_code & 0x7F, 0) + 1

        if device_addr not in self.devices:
            self._log_raw_response(None, "No response - device not emulated", timestamp)
            return

        device = self.devices[device_addr]
        response, operation = device.process_request(frame[:-2])

        if response:
            self._log_raw_response(response, f"Response sent ({len(response)} bytes)", timestamp)
            self._log_command(frame, response, function_code & 0x7F, device_addr, operation, timestamp)

            if response[1] & 0x80 and len(response) > 2 and response[2] == 0x01:
                self.stats.unsupported_function += 1
                self.stats.add_error(ErrorDetail(timestamp, "UNSUPPORTED", frame, f"Unsupported function 0x{function_code:02X}", None, 1))

            if operation:
                if "UNLOCKED" in operation:
                    self.stats.locks_unlocked += operation.count("UNLOCKED")
                if "CLOSED" in operation:
                    self.stats.locks_locked += operation.count("CLOSED")
                if self.lock_state_callback:
                    self.lock_state_callback(device_addr, operation)

            time.sleep(0.002)
            if self.serial_port:
                self.serial_port.write(response)
            self.stats.bytes_sent += len(response); self.stats.responses_sent += 1

    # ------------- Logging helpers -------------

    def _log_raw_frame(self, frame: bytes, timestamp: str):
        if not self.command_log_callback: return
        device_addr = frame[0] if len(frame) else 0
        function_code = frame[1] if len(frame) > 1 else 0
        fnames = {
            0x01: "Read Coils", 0x02: "Read Discrete Inputs", 0x03: "Read Holding Registers",
            0x04: "Read Input Registers", 0x05: "Write Single Coil", 0x06: "Write Single Register",
            0x0F: "Write Multiple Coils", 0x10: "Write Multiple Registers"
        }
        fname = fnames.get(function_code & 0x7F, f"Unknown (0x{function_code:02X})")
        crc_ok = verify_crc(frame) if len(frame) >= 4 else False
        log_entry = CommandLog(timestamp, device_addr, function_code & 0x7F, fname, frame, b'',
                               f"Frame length: {len(frame)} bytes, CRC: {'✓ Valid' if crc_ok else '✗ Invalid'}",
                               "Received (processing...)")
        self.command_log_callback(log_entry)

    def _log_raw_response(self, response: Optional[bytes], description: str, timestamp: str):
        if not self.command_log_callback: return
        if response:
            log_entry = CommandLog(timestamp, response[0] if len(response) else 0,
                                   (response[1] & 0x7F) if len(response) > 1 else 0,
                                   "Response", b'', response, description, f"Sent {len(response)} bytes")
        else:
            log_entry = CommandLog(timestamp, 0, 0, "No Response", b'', b'', description, "No response sent")
        self.command_log_callback(log_entry)

    def _log_command(self, request: bytes, response: bytes, function_code: int, device_addr: int, operation: Optional[str], timestamp: str):
        if not self.command_log_callback: return
        fnames = {
            0x01: "Read Coils", 0x02: "Read Discrete Inputs", 0x03: "Read Holding Registers",
            0x04: "Read Input Registers", 0x05: "Write Single Coil", 0x06: "Write Single Register",
            0x0F: "Write Multiple Coils", 0x10: "Write Multiple Registers"
        }
        fname = fnames.get(function_code, f"Unknown (0x{function_code:02X})")
        params, result = "", ""
        try:
            if function_code in [0x01, 0x02]:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                params = f"Start: 0x{sa:04X} ({sa}), Count: {cnt}"
                if len(response) > 3 and not (response[1] & 0x80):
                    bc = response[2]
                    data_bytes = response[3:3+bc]
                    result = f"Returned {bc} bytes: {data_bytes.hex(' ').upper()}"
                else:
                    result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 else "Exception"
            elif function_code in [0x03, 0x04]:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                params = f"Start: 0x{sa:04X} ({sa}), Count: {cnt}"
                if len(response) > 3 and not (response[1] & 0x80):
                    bc = response[2]
                    result = f"Returned {bc // 2} registers ({bc} bytes)"
                else:
                    result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 else "Exception"
            elif function_code == 0x05:
                a = struct.unpack('>H', request[2:4])[0]
                v = struct.unpack('>H', request[4:6])[0]
                st = "OPEN/UNLOCK (bit→0)" if v == 0xFF00 else "CLOSE/LOCK (bit→1)" if v == 0x0000 else f"Invalid (0x{v:04X})"
                params = f"Lock #{a+1} (0x{a:04X}), Value: {st}"
                result = operation if operation else ("Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else "Success")
            elif function_code == 0x06:
                a = struct.unpack('>H', request[2:4])[0]
                v = struct.unpack('>H', request[4:6])[0]
                params = f"Register: 0x{a:04X} ({a}), Value: 0x{v:04X} ({v})"
                result = "Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else "Success"
            elif function_code == 0x0F:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                bc = request[6]
                vals = request[7:7+bc]
                params = f"Start: 0x{sa:04X} (Lock #{sa+1}), Count: {cnt}, Data: {vals.hex(' ').upper()}"
                result = operation if operation else ("Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else f"Written {cnt} coils")
            elif function_code == 0x10:
                sa = struct.unpack('>H', request[2:4])[0]
                cnt = struct.unpack('>H', request[4:6])[0]
                bc = request[6]
                params = f"Start: 0x{sa:04X} ({sa}), Count: {cnt}, Bytes: {bc}"
                result = "Exception: 0x{response[2]:02X}" if len(response) > 2 and (response[1] & 0x80) else f"Written {cnt} registers"
            else:
                params = "Unsupported function"
                result = f"Exception: 0x{response[2]:02X}" if len(response) > 2 else "Error"
        except Exception as e:
            params = f"Error decoding: {e}"
            result = "Parse error"

        self.command_log_callback(CommandLog(timestamp, device_addr, function_code, fname, request, response, params, result))


# ------------- Command Log dataclass -------------

@dataclass
class CommandLog:
    timestamp: str
    device_addr: int
    function_code: int
    function_name: str
    raw_request: bytes
    raw_response: bytes
    parameters: str
    result: str

    def format_log(self) -> str:
        lines = [f"[{self.timestamp}] Device 0x{self.device_addr:02X} - {self.function_name} (0x{self.function_code:02X})"]
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


# ------------- GUI -------------

class EmulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Modbus RTU Slave Emulator V3 - CU48 (Fixed+ Lockstate)")
        self.root.geometry("1200x900")
        self.emulator = None
        self.log_update_timer = None
        self.lock_buttons = {}

        self._create_widgets()
        self._refresh_ports()

    def _create_widgets(self):
        config_frame = ttk.LabelFrame(self.root, text="Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(config_frame, textvariable=self.port_var, width=15, state='readonly')
        self.port_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Button(config_frame, text="Refresh", command=self._refresh_ports).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(config_frame, text="Baud Rate:").grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.baudrate_var = tk.StringVar(value="115200")
        ttk.Combobox(config_frame, textvariable=self.baudrate_var,
                     values=["9600", "19200", "38400", "57600", "115200"],
                     width=10, state='readonly').grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)

        ttk.Label(config_frame, text="Num Devices:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.num_devices_var = tk.IntVar(value=1)
        ttk.Spinbox(config_frame, from_=1, to=10, textvariable=self.num_devices_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        self.cu48_zero_means_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="CU48 compat: count=0 → read 48", variable=self.cu48_zero_means_all_var).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)

        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=2, column=0, columnspan=5, padx=5, pady=5, sticky=tk.W)
        self.start_btn = ttk.Button(button_frame, text="Start Emulator", command=self._start_emulator)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(button_frame, text="Stop Emulator", command=self._stop_emulator, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        self.status_label = ttk.Label(status_frame, text="Status: Stopped", foreground="red")
        self.status_label.pack()

        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        notebook = ttk.Notebook(content_frame); notebook.pack(fill=tk.BOTH, expand=True)

        lock_control_frame = ttk.Frame(notebook); notebook.add(lock_control_frame, text="Lock Control (CU48)")
        device_select_frame = ttk.Frame(lock_control_frame); device_select_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(device_select_frame, text="Device:").pack(side=tk.LEFT, padx=5)
        self.selected_device_var = tk.IntVar(value=1)
        self.device_selector = ttk.Spinbox(device_select_frame, from_=1, to=10, textvariable=self.selected_device_var, width=5, command=self._update_lock_display)
        self.device_selector.pack(side=tk.LEFT, padx=5)
        ttk.Label(device_select_frame, text="(48 locks per device)").pack(side=tk.LEFT, padx=5)

        lock_canvas = tk.Canvas(lock_control_frame)
        lock_scrollbar = ttk.Scrollbar(lock_control_frame, orient="vertical", command=lock_canvas.yview)
        self.lock_grid_frame = ttk.Frame(lock_canvas)
        lock_canvas.configure(yscrollcommand=lock_scrollbar.set)
        lock_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lock_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lock_canvas.create_window((0, 0), window=self.lock_grid_frame, anchor="nw")
        self.lock_grid_frame.bind("<Configure>", lambda e: lock_canvas.configure(scrollregion=lock_canvas.bbox("all")))
        self._create_lock_controls()

        stats_frame = ttk.Frame(notebook); notebook.add(stats_frame, text="Statistics")
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=20, width=90, font=("Courier New", 9))
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        error_frame = ttk.Frame(notebook); notebook.add(error_frame, text="Last 5 Errors")
        self.error_text = scrolledtext.ScrolledText(error_frame, height=20, width=90, font=("Courier New", 8), foreground="red")
        self.error_text.pack(fill=tk.BOTH, expand=True)

        command_log_frame = ttk.Frame(notebook); notebook.add(command_log_frame, text="Command Log")
        self.command_log_text = scrolledtext.ScrolledText(command_log_frame, height=20, width=90, font=("Courier New", 8), foreground="blue")
        self.command_log_text.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.Frame(notebook); notebook.add(log_frame, text="System Log")
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=90, font=("Courier New", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        action_frame = ttk.Frame(self.root); action_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(action_frame, text="Clear System Log", command=self._clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Clear Command Log", command=self._clear_command_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Clear Errors", command=self._clear_errors).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Save Statistics", command=self._save_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Save Command Log", command=self._save_command_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Reset Statistics", command=self._reset_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Close All Locks", command=self._close_all_locks).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Open All Locks", command=self._open_all_locks).pack(side=tk.LEFT, padx=5)

    def _create_lock_controls(self):
        info_label = ttk.Label(self.lock_grid_frame, text="48 CU48 Locks - Green=Closed (1), Red=Open (0)")
        info_label.grid(row=0, column=0, columnspan=8, pady=5)
        self.lock_buttons = {}
        for i in range(48):
            row = (i // 8) + 1; col = i % 8
            frame = ttk.Frame(self.lock_grid_frame, relief=tk.RAISED, borderwidth=1)
            frame.grid(row=row, column=col, padx=2, pady=2, sticky=tk.NSEW)
            ttk.Label(frame, text=f"Lock {i+1}").pack()
            btn = tk.Button(frame, text="CLOSED", bg="green", fg="white", command=lambda idx=i: self._toggle_lock(idx))
            btn.pack(fill=tk.BOTH, expand=True)
            self.lock_buttons[i] = btn

    def _update_lock_display(self):
        if not self.emulator: return
        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices: return
        dev = self.emulator.devices[device_id]
        for i in range(48):
            if dev.coils[i]:
                self.lock_buttons[i].config(text="CLOSED", bg="green")
            else:
                self.lock_buttons[i].config(text="OPEN", bg="red")

    def _toggle_lock(self, lock_idx: int):
        if not self.emulator:
            messagebox.showwarning("Warning", "Emulator not running"); return
        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices:
            messagebox.showerror("Error", f"Device {device_id} not emulated"); return
        dev = self.emulator.devices[device_id]
        dev.coils[lock_idx] = not dev.coils[lock_idx]
        dev._set_bit(lock_idx, closed=dev.coils[lock_idx])
        self._update_lock_display()
        self._log(f"Device {device_id} Lock #{lock_idx+1} set to {'CLOSED' if dev.coils[lock_idx] else 'OPEN'}")

    def _close_all_locks(self):
        if not self.emulator:
            messagebox.showwarning("Warning", "Emulator not running"); return
        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices: return
        dev = self.emulator.devices[device_id]; dev.coils = [True]*48; dev.status_reg[:] = b'\xFF'*6
        self._update_lock_display(); self._log(f"Device {device_id}: All locks CLOSED")

    def _open_all_locks(self):
        if not self.emulator:
            messagebox.showwarning("Warning", "Emulator not running"); return
        device_id = self.selected_device_var.get()
        if device_id not in self.emulator.devices: return
        dev = self.emulator.devices[device_id]; dev.coils = [False]*48; dev.status_reg[:] = b'\x00'*6
        self._update_lock_display(); self._log(f"Device {device_id}: All locks OPEN")

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports: self.port_combo.current(0)

    def _start_emulator(self):
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port"); return
        baudrate = int(self.baudrate_var.get())
        num_devices = self.num_devices_var.get()
        cu48_zero_means_all = self.cu48_zero_means_all_var.get()
        try:
            self.emulator = ModbusRTUEmulator(num_devices, cu48_zero_means_all)
            self.emulator.set_lock_state_callback(lambda did, op: self._log(f"Device {did}: {op}"))
            self.emulator.set_command_log_callback(self._on_command_received)
            self.emulator.start(port, baudrate)
            mode = "count=0→48" if cu48_zero_means_all else "spec strict (count=0 → exception 0x03)"
            self.status_label.config(text=f"Status: Running on {port} @ {baudrate} baud, {num_devices} CU48 device(s), {mode}", foreground="green")
            self.start_btn.config(state=tk.DISABLED); self.stop_btn.config(state=tk.NORMAL)
            self._log(f"CU48 Emulator V3 (Fixed+ Lockstate) started: {port} @ {baudrate} baud; {mode}")
            self._update_lock_display(); self._update_statistics()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _stop_emulator(self):
        if self.emulator:
            self.emulator.stop(); self._log("\n" + self.emulator.stats.get_summary()); self.emulator = None
        self.status_label.config(text="Status: Stopped", foreground="red")
        self.start_btn.config(state=tk.NORMAL); self.stop_btn.config(state=tk.DISABLED)
        if self.log_update_timer: self.root.after_cancel(self.log_update_timer)

    def _update_statistics(self):
        if self.emulator and self.emulator.running:
            self.stats_text.delete(1.0, tk.END); self.stats_text.insert(1.0, self.emulator.stats.get_summary())
            self.error_text.delete(1.0, tk.END); self.error_text.insert(1.0, self.emulator.stats.get_recent_errors_summary())
            self._update_lock_display()
            self.log_update_timer = self.root.after(1000, self._update_statistics)

    def _on_command_received(self, command_log: 'CommandLog'):
        log_text = command_log.format_log()
        self.command_log_text.insert(tk.END, log_text + "\n")
        self.command_log_text.see(tk.END)
        if "UNLOCK" in command_log.result or "CLOSED" in command_log.result:
            self._log(f"CMD: Device {command_log.device_addr} - {command_log.result}")

    def _log(self, message: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.log_text.insert(tk.END, f"[{ts}] {message}\n")
        self.log_text.see(tk.END)

    def _clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def _clear_command_log(self):
        self.command_log_text.delete(1.0, tk.END); self._log("Command log cleared")

    def _clear_errors(self):
        if self.emulator:
            self.emulator.stats.recent_errors.clear()
            self.error_text.delete(1.0, tk.END); self.error_text.insert(1.0, "No recent errors")
            self._log("Error list cleared")

    def _save_statistics(self):
        if not self.emulator:
            messagebox.showwarning("Warning", "No emulator running"); return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"modbus_cu48_stats_{ts}.txt"
        try:
            with open(fn, 'w') as f:
                f.write(self.emulator.stats.get_summary()); f.write("\n\n"); f.write(self.emulator.stats.get_recent_errors_summary())
            messagebox.showinfo("Success", f"Statistics saved to {fn}"); self._log(f"Statistics saved to {fn}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save statistics: {e}")

    def _save_command_log(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"modbus_cu48_commands_{ts}.log"
        try:
            log_content = self.command_log_text.get(1.0, tk.END)
            if not log_content.strip():
                messagebox.showwarning("Warning", "Command log is empty"); return
            with open(fn, 'w') as f:
                f.write("=" * 70 + "\n")
                f.write("MODBUS RTU CU48 EMULATOR - COMMAND LOG\n")
                f.write("=" * 70 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 70 + "\n\n")
                f.write(log_content)
            messagebox.showinfo("Success", f"Command log saved to {fn}"); self._log(f"Command log saved to {fn}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save command log: {e}")

    def _reset_statistics(self):
        if self.emulator:
            self.emulator.stats.reset(); self._log("Statistics reset")

    def on_closing(self):
        if self.emulator and self.emulator.running: self._stop_emulator()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = EmulatorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
