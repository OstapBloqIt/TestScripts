#!/usr/bin/env python3
"""
Modbus RTU Slave Emulator for Windows
Emulates 1-10 Modbus slave devices on RS485 (half-duplex)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
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

    def reset(self):
        """Reset all statistics"""
        self.__init__()

    def get_summary(self) -> str:
        """Get formatted statistics summary"""
        elapsed = time.time() - self.start_time
        lines = [
            "=" * 60,
            "MODBUS RTU SLAVE EMULATOR - STATISTICS",
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


class ModbusSlaveDevice:
    """Single Modbus slave device with registers and coils"""

    def __init__(self, device_id: int):
        self.device_id = device_id
        # Initialize memory maps
        self.coils = [False] * 256  # Coils (read/write bits)
        self.discrete_inputs = [False] * 256  # Discrete inputs (read-only bits)
        self.holding_registers = [0] * 256  # Holding registers (read/write)
        self.input_registers = [0] * 256  # Input registers (read-only)

        # Set some default values based on the captured traffic
        if device_id == 0:
            self.holding_registers[0x0F] = 0xE230  # 57,904
            self.holding_registers[0xF5] = 0x0002
            self.holding_registers[0xF6] = 0x0004

    def read_coils(self, start_addr: int, count: int) -> bytes:
        """Read coil status (Function 01)"""
        if start_addr + count > len(self.coils):
            return self._exception_response(0x01, 0x02)  # Illegal data address

        # Pack bits into bytes
        byte_count = (count + 7) // 8
        result = bytearray([byte_count])

        for byte_idx in range(byte_count):
            byte_val = 0
            for bit_idx in range(8):
                coil_idx = start_addr + byte_idx * 8 + bit_idx
                if coil_idx < start_addr + count and coil_idx < len(self.coils):
                    if self.coils[coil_idx]:
                        byte_val |= (1 << bit_idx)
            result.append(byte_val)

        return bytes(result)

    def read_discrete_inputs(self, start_addr: int, count: int) -> bytes:
        """Read discrete inputs (Function 02)"""
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
        """Read holding registers (Function 03)"""
        if start_addr + count > len(self.holding_registers):
            return self._exception_response(0x03, 0x02)

        byte_count = count * 2
        result = bytearray([byte_count])

        for i in range(count):
            reg_val = self.holding_registers[start_addr + i]
            result.extend(struct.pack('>H', reg_val))  # Big-endian

        return bytes(result)

    def read_input_registers(self, start_addr: int, count: int) -> bytes:
        """Read input registers (Function 04)"""
        if start_addr + count > len(self.input_registers):
            return self._exception_response(0x04, 0x02)

        byte_count = count * 2
        result = bytearray([byte_count])

        for i in range(count):
            reg_val = self.input_registers[start_addr + i]
            result.extend(struct.pack('>H', reg_val))

        return bytes(result)

    def write_single_coil(self, addr: int, value: int) -> bytes:
        """Write single coil (Function 05)"""
        if addr >= len(self.coils):
            return self._exception_response(0x05, 0x02)

        if value == 0xFF00:
            self.coils[addr] = True
        elif value == 0x0000:
            self.coils[addr] = False
        else:
            return self._exception_response(0x05, 0x03)  # Illegal data value

        # Echo back the request
        return struct.pack('>HH', addr, value)

    def write_single_register(self, addr: int, value: int) -> bytes:
        """Write single register (Function 06)"""
        if addr >= len(self.holding_registers):
            return self._exception_response(0x06, 0x02)

        self.holding_registers[addr] = value & 0xFFFF

        # Echo back the request
        return struct.pack('>HH', addr, value)

    def write_multiple_coils(self, start_addr: int, count: int, values: bytes) -> bytes:
        """Write multiple coils (Function 15/0x0F)"""
        if start_addr + count > len(self.coils):
            return self._exception_response(0x0F, 0x02)

        for i in range(count):
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < len(values):
                self.coils[start_addr + i] = bool(values[byte_idx] & (1 << bit_idx))

        # Echo back start address and count
        return struct.pack('>HH', start_addr, count)

    def write_multiple_registers(self, start_addr: int, count: int, values: bytes) -> bytes:
        """Write multiple registers (Function 16/0x10)"""
        if start_addr + count > len(self.holding_registers):
            return self._exception_response(0x10, 0x02)

        if len(values) != count * 2:
            return self._exception_response(0x10, 0x03)

        for i in range(count):
            reg_val = struct.unpack('>H', values[i*2:(i+1)*2])[0]
            self.holding_registers[start_addr + i] = reg_val

        # Echo back start address and count
        return struct.pack('>HH', start_addr, count)

    def _exception_response(self, function_code: int, exception_code: int) -> bytes:
        """Create Modbus exception response"""
        return bytes([function_code | 0x80, exception_code])

    def process_request(self, request: bytes) -> bytes:
        """Process a Modbus request and return response"""
        if len(request) < 4:
            return None

        device_addr = request[0]
        if device_addr != self.device_id:
            return None  # Not for this device

        function_code = request[1]

        try:
            if function_code == 0x01:  # Read Coils
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_coils(start_addr, count)

            elif function_code == 0x02:  # Read Discrete Inputs
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_discrete_inputs(start_addr, count)

            elif function_code == 0x03:  # Read Holding Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_holding_registers(start_addr, count)

            elif function_code == 0x04:  # Read Input Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                data = self.read_input_registers(start_addr, count)

            elif function_code == 0x05:  # Write Single Coil
                addr = struct.unpack('>H', request[2:4])[0]
                value = struct.unpack('>H', request[4:6])[0]
                data = self.write_single_coil(addr, value)

            elif function_code == 0x06:  # Write Single Register
                addr = struct.unpack('>H', request[2:4])[0]
                value = struct.unpack('>H', request[4:6])[0]
                data = self.write_single_register(addr, value)

            elif function_code == 0x0F:  # Write Multiple Coils
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                byte_count = request[6]
                values = request[7:7+byte_count]
                data = self.write_multiple_coils(start_addr, count, values)

            elif function_code == 0x10:  # Write Multiple Registers
                start_addr = struct.unpack('>H', request[2:4])[0]
                count = struct.unpack('>H', request[4:6])[0]
                byte_count = request[6]
                values = request[7:7+byte_count]
                data = self.write_multiple_registers(start_addr, count, values)

            else:
                # Unsupported function code - return exception directly
                response = bytes([device_addr]) + self._exception_response(function_code, 0x01)
                response += crc16_bytes(response)
                return response

            # Build response: device_addr + function_code + data + CRC
            response = bytes([device_addr, function_code]) + data
            response += crc16_bytes(response)
            return response

        except Exception as e:
            # Return exception response on error
            response = bytes([device_addr, function_code | 0x80, 0x04])  # Slave device failure
            response += crc16_bytes(response)
            return response


class ModbusRTUEmulator:
    """Main Modbus RTU emulator class"""

    def __init__(self, num_devices: int):
        self.num_devices = num_devices
        self.devices = {i: ModbusSlaveDevice(i) for i in range(0, num_devices)}
        self.stats = Statistics()
        self.serial_port = None
        self.running = False
        self.thread = None

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

    def _receive_loop(self):
        """Main receive loop for processing Modbus requests"""
        buffer = bytearray()
        last_receive_time = time.time()

        while self.running:
            try:
                # Check for incoming data
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    buffer.extend(data)
                    last_receive_time = time.time()
                    self.stats.bytes_received += len(data)
                else:
                    # Check for end of frame (3.5 character times @ baudrate)
                    # For 9600 baud: ~3.6ms, we'll use 10ms to be safe
                    if len(buffer) > 0 and (time.time() - last_receive_time) > 0.01:
                        self._process_frame(bytes(buffer))
                        buffer.clear()

                    time.sleep(0.001)  # Small delay to prevent CPU spinning

            except Exception as e:
                print(f"Error in receive loop: {e}")
                time.sleep(0.1)

    def _process_frame(self, frame: bytes):
        """Process a received Modbus frame"""
        self.stats.total_requests += 1

        # Minimum Modbus frame: addr(1) + func(1) + data(0+) + crc(2) = 4 bytes
        if len(frame) < 4:
            self.stats.framing_errors += 1
            self.stats.invalid_requests += 1
            return

        # Verify CRC
        if not verify_crc(frame):
            self.stats.crc_errors += 1
            self.stats.invalid_requests += 1
            return

        # Extract device address and function code
        device_addr = frame[0]
        function_code = frame[1]

        # Update statistics
        self.stats.valid_requests += 1
        self.stats.device_requests[device_addr] = self.stats.device_requests.get(device_addr, 0) + 1
        self.stats.function_code_counts[function_code] = self.stats.function_code_counts.get(function_code, 0) + 1

        # Check if this device is emulated
        if device_addr not in self.devices:
            # Not our device, ignore (no response on Modbus RTU)
            return

        # Process request and generate response
        device = self.devices[device_addr]
        response = device.process_request(frame[:-2])  # Remove CRC before processing

        if response:
            # Check if function code is supported
            if response[1] & 0x80:  # Exception response
                if response[2] == 0x01:  # Illegal function
                    self.stats.unsupported_function += 1

            # Send response (half-duplex: wait a bit before responding)
            time.sleep(0.002)  # 2ms response delay
            self.serial_port.write(response)
            self.stats.bytes_sent += len(response)
            self.stats.responses_sent += 1


class EmulatorGUI:
    """Windows GUI for Modbus RTU Emulator"""

    def __init__(self, root):
        self.root = root
        self.root.title("Modbus RTU Slave Emulator")
        self.root.geometry("900x700")

        self.emulator = None
        self.log_update_timer = None

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
        self.baudrate_var = tk.StringVar(value="9600")
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

        # Statistics Frame
        stats_frame = ttk.LabelFrame(self.root, text="Statistics", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create notebook for tabs
        notebook = ttk.Notebook(stats_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Real-time stats tab
        realtime_frame = ttk.Frame(notebook)
        notebook.add(realtime_frame, text="Real-time")

        self.stats_text = scrolledtext.ScrolledText(realtime_frame, height=15, width=80,
                                                     font=("Courier New", 9))
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Communication Log")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80,
                                                   font=("Courier New", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(action_frame, text="Clear Log", command=self._clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Save Statistics", command=self._save_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Reset Statistics", command=self._reset_statistics).pack(side=tk.LEFT, padx=5)

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
            self.emulator.start(port, baudrate)

            self.status_label.config(text=f"Status: Running on {port} @ {baudrate} baud, {num_devices} device(s)",
                                    foreground="green")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)

            self._log(f"Emulator started: {port} @ {baudrate} baud")
            self._log(f"Emulating devices: {', '.join([str(i) for i in range(0, num_devices)])}")

            # Start statistics update timer
            self._update_statistics()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _stop_emulator(self):
        """Stop the Modbus emulator"""
        if self.emulator:
            self.emulator.stop()

            # Show final statistics
            final_stats = self.emulator.stats.get_summary()
            self._log("\n" + final_stats)

            self.emulator = None

        self.status_label.config(text="Status: Stopped", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        # Cancel statistics update timer
        if self.log_update_timer:
            self.root.after_cancel(self.log_update_timer)

    def _update_statistics(self):
        """Update statistics display"""
        if self.emulator and self.emulator.running:
            stats_summary = self.emulator.stats.get_summary()
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_summary)

            # Schedule next update
            self.log_update_timer = self.root.after(1000, self._update_statistics)

    def _log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

    def _clear_log(self):
        """Clear the log"""
        self.log_text.delete(1.0, tk.END)

    def _save_statistics(self):
        """Save statistics to file"""
        if not self.emulator:
            messagebox.showwarning("Warning", "No emulator running")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"modbus_stats_{timestamp}.txt"

        try:
            with open(filename, 'w') as f:
                f.write(self.emulator.stats.get_summary())

            messagebox.showinfo("Success", f"Statistics saved to {filename}")
            self._log(f"Statistics saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save statistics: {e}")

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
