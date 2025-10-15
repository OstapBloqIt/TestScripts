#!/usr/bin/env python3
"""
Modbus RTU Slave Emulator V3 (CU48) - Lockstate Register Version
- Maintains a 48-bit internal status register per device (starts all 1s = closed)
- Read Coils (0x01) serves the register state
- Write Single/Multiple Coil updates both the register and the coils
- Write Single Coil semantics changed: 0xFF00 => OPEN/UNLOCK (bit -> 0), 0x0000 => CLOSE/LOCK (bit -> 1)
- Includes robust frame splitting and consistent response wrapping (from Fixed+)
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
    return len(message) >= 4 and (message[-2:] == crc16_bytes(message[:-2]))

@dataclass
class ErrorDetail:
    timestamp: str
    error_type: str
    frame: bytes
    description: str
    expected_value: Optional[bytes] = None
    error_position: Optional[int] = None

    def format_detailed(self) -> str:
        return f"[{self.timestamp}] {self.error_type} ERROR: {self.description}\\n" + self.frame.hex()

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

    def add_error(self, e: 'ErrorDetail'):
        self.recent_errors.append(e)

    def reset(self): self.__init__()

    def get_summary(self) -> str:
        return f"Total: {self.total_requests}, Valid: {self.valid_requests}, Invalid: {self.invalid_requests}"

    def get_recent_errors_summary(self) -> str:
        return "\\n".join([er.format_detailed() for er in self.recent_errors]) or "No recent errors"

class CU48Device:
    def __init__(self, device_id: int):
        self.device_id = device_id
        self.coils = [True] * 48
        self.status_reg = bytearray([0xFF] * 6)
        self.discrete_inputs = [False] * 256
        self.holding_registers = [0] * 256
        self.input_registers = [0] * 256
        self.holding_registers[0x03] = 550
        self.holding_registers[0x0F] = 0xE230
        self.holding_registers[0xF5] = 0x0002
        self.holding_registers[0xF6] = 0x0004

    def _set_bit(self, idx: int, closed: bool):
        b = idx // 8; bit = idx % 8
        if closed: self.status_reg[b] |= (1 << bit)
        else:      self.status_reg[b] &= ~(1 << bit)

    def _sync_status_from_coils(self):
        for i, c in enumerate(self.coils):
            self._set_bit(i, closed=c)

    def read_coils(self, start_addr: int, count: int) -> bytes:
        if count == 0: return bytes([0x01 | 0x80, 0x03])
        if start_addr >= 48 or start_addr + count > 48: return bytes([0x01 | 0x80, 0x02])
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

    def write_single_coil(self, addr: int, value: int) -> Tuple[bytes, Optional[str]]:
        if addr >= 48: return (bytes([0x05 | 0x80, 0x02]), None)
        if value == 0xFF00:
            self.coils[addr] = False; self._set_bit(addr, closed=False); op = f"LOCK #{addr+1} OPENED/UNLOCKED"
        elif value == 0x0000:
            self.coils[addr] = True;  self._set_bit(addr, closed=True);  op = f"LOCK #{addr+1} CLOSED/LOCKED"
        else:
            return (bytes([0x05 | 0x80, 0x03]), None)
        return (struct.pack('>HH', addr, value), op)

    def write_multiple_coils(self, start_addr: int, count: int, values: bytes) -> Tuple[bytes, Optional[str]]:
        if count == 0: return (bytes([0x0F | 0x80, 0x03]), None)
        if start_addr >= 48 or start_addr + count > 48: return (bytes([0x0F | 0x80, 0x02]), None)
        ops = []
        for i in range(count):
            b = i // 8; bit = i % 8
            if b < len(values):
                incoming = bool(values[b] & (1 << bit))
                idx = start_addr + i
                self.coils[idx] = incoming
                self._set_bit(idx, closed=incoming)
                ops.append(f"Lock #{idx+1} {'CLOSED/LOCKED' if incoming else 'OPENED/UNLOCKED'}")
        return (struct.pack('>HH', start_addr, count), "; ".join(ops) if ops else None)

    def _exception(self, fc: int, code: int) -> bytes: return bytes([fc | 0x80, code])

    def _build_response(self, device_addr: int, fc: int, payload: bytes) -> bytes:
        resp = (bytes([device_addr]) + payload) if (len(payload)==2 and (payload[0] & 0x80)) else (bytes([device_addr, fc]) + payload)
        return resp + crc16_bytes(resp)

    def process_request(self, request: bytes) -> Tuple[Optional[bytes], Optional[str]]:
        if len(request) < 4: return None, None
        device_addr = request[0]
        if device_addr != self.device_id: return None, None
        fc = request[1]
        try:
            if fc == 0x01:
                sa = struct.unpack('>H', request[2:4])[0]; cnt = struct.unpack('>H', request[4:6])[0]
                return (self._build_response(device_addr, fc, self.read_coils(sa, cnt)), None)
            if fc == 0x05:
                a = struct.unpack('>H', request[2:4])[0]; v = struct.unpack('>H', request[4:6])[0]
                payload, op = self.write_single_coil(a, v)
                return (self._build_response(device_addr, fc, payload), op)
            if fc == 0x0F:
                sa = struct.unpack('>H', request[2:4])[0]; cnt = struct.unpack('>H', request[4:6])[0]
                bc = request[6]; vals = request[7:7+bc]
                payload, op = self.write_multiple_coils(sa, cnt, vals)
                return (self._build_response(device_addr, fc, payload), op)
            return (self._build_response(device_addr, fc, self._exception(fc, 0x01)), None)
        except Exception:
            return (self._build_response(device_addr, fc, self._exception(fc, 0x04)), None)

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
        return f"[{self.timestamp}] Dev 0x{self.device_addr:02X} {self.function_name} 0x{self.function_code:02X}\\n"

class ModbusRTUEmulator:
    def __init__(self, num_devices: int):
        self.devices = {i: CU48Device(i) for i in range(1, num_devices + 1)}
        self.stats = Statistics()
        self.serial_port = None
        self.running = False
        self.thread = None
        self.lock_state_callback = None
        self.command_log_callback = None
    def set_lock_state_callback(self, cb): self.lock_state_callback = cb
    def set_command_log_callback(self, cb): self.command_log_callback = cb
    def start(self, port: str, baudrate: int, timeout: float = 0.1):
        self.serial_port = serial.Serial(port=port, baudrate=baudrate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=timeout)
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True); self.thread.start(); return True
    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=2)
        if self.serial_port and self.serial_port.is_open: self.serial_port.close()
    def _char_time_seconds(self) -> float:
        baud = max(300, int(self.serial_port.baudrate) if self.serial_port else 115200); return 11.0 / baud
    def _frame_gap_seconds(self) -> float: return max(0.0015, 3.5 * self._char_time_seconds())
    def _receive_loop(self):
        buf = bytearray(); last = time.time()
        while self.running:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data: buf.extend(data); last = time.time(); self.stats.bytes_received += len(data)
                else:
                    if len(buf) > 0 and (time.time()-last) > self._frame_gap_seconds(): self._extract_and_process(buf)
                    time.sleep(0.001)
            except Exception as e:
                time.sleep(0.1)
    def _extract_and_process(self, buf: bytearray):
        while len(buf) >= 4:
            found=False
            for i in range(4, len(buf)+1):
                if verify_crc(buf[:i]):
                    frame = bytes(buf[:i]); del buf[:i]; self._process_frame(frame); found=True; break
            if not found: break
    def _process_frame(self, frame: bytes):
        self.stats.total_requests += 1
        if not verify_crc(frame): self.stats.crc_errors += 1; self.stats.invalid_requests += 1; return
        addr = frame[0]; fc = frame[1]
        self.stats.valid_requests += 1
        if addr not in self.devices: return
        dev = self.devices[addr]
        resp, op = dev.process_request(frame[:-2])
        if resp and self.serial_port:
            time.sleep(0.002); self.serial_port.write(resp); self.stats.bytes_sent += len(resp); self.stats.responses_sent += 1

class EmulatorGUI:
    def __init__(self, root):
        self.root = root; self.root.title("CU48 Emulator (Lockstate)"); self.root.geometry("900x600")
        self.emu = None; self.log_update_timer = None
        self._build(); self._refresh_ports()
    def _build(self):
        frm = ttk.LabelFrame(self.root, text="Config", padding=10); frm.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(frm, text="COM Port:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.port_var = tk.StringVar(); self.port_combo = ttk.Combobox(frm, textvariable=self.port_var, width=15, state='readonly'); self.port_combo.grid(row=0, column=1, sticky=tk.W)
        ttk.Button(frm, text="Refresh", command=self._refresh_ports).grid(row=0, column=2, padx=5)
        ttk.Label(frm, text="Baud:").grid(row=0, column=3, sticky=tk.W, padx=5)
        self.baud_var = tk.StringVar(value="115200"); ttk.Combobox(frm, textvariable=self.baud_var, values=["9600","19200","38400","57600","115200"], width=10, state='readonly').grid(row=0, column=4, sticky=tk.W)
        ttk.Label(frm, text="Devices:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.num_var = tk.IntVar(value=1); ttk.Spinbox(frm, from_=1, to=10, textvariable=self.num_var, width=10).grid(row=1, column=1, sticky=tk.W)
        btnf = ttk.Frame(frm); btnf.grid(row=2, column=0, columnspan=5, sticky=tk.W)
        self.start_btn = ttk.Button(btnf, text="Start", command=self._start); self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btnf, text="Stop", command=self._stop, state=tk.DISABLED); self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.status = ttk.Label(self.root, text="Status: Stopped"); self.status.pack(padx=10, pady=5)
        self.log = scrolledtext.ScrolledText(self.root, height=20, width=100, font=("Courier New", 9)); self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports: self.port_combo.current(0)
    def _start(self):
        port = self.port_var.get()
        if not port: messagebox.showerror("Error","Select COM port"); return
        baud = int(self.baud_var.get()); n = self.num_var.get()
        try:
            self.emu = ModbusRTUEmulator(n); self.emu.start(port, baud)
            self.start_btn.config(state=tk.DISABLED); self.stop_btn.config(state=tk.NORMAL)
            self.status.config(text=f"Status: Running on {port}@{baud} with {n} device(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    def _stop(self):
        if self.emu: self.emu.stop(); self.emu=None
        self.start_btn.config(state=tk.NORMAL); self.stop_btn.config(state=tk.DISABLED)
        self.status.config(text="Status: Stopped")

def main():
    root = tk.Tk(); app = EmulatorGUI(root); root.mainloop()

if __name__ == "__main__":
    main()
