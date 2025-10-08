# RS485 Adapter Baud Rate Sweep Test

This test suite evaluates the performance of an RS485 adapter board by testing communication at different baud rates and measuring bit error rates (BER).

## Hardware Setup

```
PC ←→ RS485-USB Adapter ←→ [A+/B- RS485 Bus] ←→ RS485 Adapter Board ←→ ESP32-S3-Zero
                                                        ↑
                                                   [TX/RX TTL]
```

### Connections

**ESP32-S3-Zero:**
- Pin 17 (TX) → RS485 Adapter TTL TX
- Pin 18 (RX) → RS485 Adapter TTL RX
- Pin 2 → Built-in LED (status indication)

**RS485 Adapter Board:**
- TTL TX/RX → ESP32-S3-Zero pins 17/18
- A+/B- → RS485-USB adapter A+/B-

**PC:**
- USB → RS485-USB adapter
- A+/B- → RS485 Adapter Board A+/B-

## Software Components

### 1. PC-Side Python Program (`pc_baud_rate_sweep.py`)

Tests communication at baud rates: 9600, 19200, 38400, 57600, 115200 bps

**Features:**
- Sends test messages with sequence numbers and checksums
- Measures response times and calculates BER
- Tracks success rates and error counts
- Generates detailed reports (JSON + human-readable)
- Real-time progress indication

### 2. ESP32-S3 Arduino Program (`esp32_rs485_responder.ino`)

Responds to test messages from the PC

**Features:**
- Automatic baud rate detection
- Message validation with checksum verification
- LED status indication (fast blink = searching, slow blink = operational)
- Responds with ACK messages
- Serial debug output

## Installation & Setup

### PC Side

1. Install Python 3.7+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### ESP32-S3 Side

1. Install Arduino IDE with ESP32 board support
2. Select board: "ESP32S3 Dev Module"
3. Upload `esp32_rs485_responder.ino`

## Usage

### 1. Upload ESP32 Program

1. Open `esp32_rs485_responder.ino` in Arduino IDE
2. Select the correct board and port
3. Upload the program
4. Open Serial Monitor (115200 bps) to see debug output

### 2. Run PC Test

```bash
# Basic usage
python pc_baud_rate_sweep.py COM3

# Custom parameters
python pc_baud_rate_sweep.py COM3 --timeout 3.0 --messages 200

# Linux/Mac example
python pc_baud_rate_sweep.py /dev/ttyUSB0
```

**Parameters:**
- `port`: Serial port (required) - e.g., COM3, /dev/ttyUSB0
- `--timeout`: Response timeout in seconds (default: 2.0)
- `--messages`: Messages per baud rate (default: 100)

## Test Protocol

### Message Format

**PC → ESP32:**
```
RS485_TEST_MESSAGE_<sequence>_<checksum>\n
```
Example: `RS485_TEST_MESSAGE_0001_a1b2c3d4`

**ESP32 → PC:**
```
ACK_RS485_TEST_MESSAGE_<sequence>_<checksum>\n
```
Example: `ACK_RS485_TEST_MESSAGE_0001_a1b2c3d4`

### Test Sequence

1. **Baud Rate Setup**: PC configures serial port to test baud rate
2. **Message Transmission**: PC sends 100 test messages (configurable)
3. **Response Validation**: PC validates ESP32 responses
4. **Statistics Collection**: Success rate, BER, response times
5. **Next Baud Rate**: Repeat for all configured baud rates
6. **Report Generation**: Create detailed test results

## Output Reports

The test generates two report files:

### JSON Report (`rs485_baud_sweep_report_YYYYMMDD_HHMMSS.json`)
Machine-readable detailed test data including:
- Test configuration and timing
- Detailed results per baud rate
- Error logs and statistics
- Summary statistics

### Text Report (`rs485_baud_sweep_report_YYYYMMDD_HHMMSS.txt`)
Human-readable summary including:
- Test overview and duration
- Success rates per baud rate
- Best/worst performing baud rates
- Error summaries

## LED Status Indicators (ESP32)

- **Fast Blink (200ms)**: Searching for baud rate
- **Slow Blink (1000ms)**: Operational, baud rate detected
- **Rapid Blink (50ms)**: Baud rate successfully detected
- **Brief Flash (10ms)**: Successful message processed

## Troubleshooting

### Common Issues

1. **"Permission denied" on serial port**
   - Windows: Check Device Manager for correct COM port
   - Linux: Add user to dialout group: `sudo usermod -a -G dialout $USER`

2. **No responses from ESP32**
   - Check wiring connections
   - Verify ESP32 program uploaded correctly
   - Check Serial Monitor for ESP32 debug output
   - Ensure RS485 adapter has proper power

3. **High error rates**
   - Check for loose connections
   - Verify RS485 termination resistors
   - Test with shorter cables
   - Check for electrical interference

4. **Timeout errors**
   - Increase timeout with `--timeout` parameter
   - Check RS485 adapter configuration
   - Verify baud rate support on hardware

### Debug Steps

1. **Verify Hardware**:
   - Check all connections
   - Test with multimeter for continuity
   - Verify power supply to RS485 adapter

2. **Test ESP32 Standalone**:
   - Monitor ESP32 Serial output during test
   - Verify LED blinking patterns
   - Check message reception in debug output

3. **Test PC Communication**:
   - Use terminal program to manually send messages
   - Verify serial port settings
   - Test with different baud rates manually

## Expected Results

Typical performance expectations:
- **9600-57600 bps**: Near 100% success rate, low BER
- **115200 bps**: May show increased errors depending on cable quality and length
- **Response times**: Should be consistent per baud rate (lower baud = longer response time)

## Customization

### Adding Baud Rates

**PC side** (`pc_baud_rate_sweep.py`):
```python
self.baud_rates = [9600, 19200, 38400, 57600, 115200, 230400]
```

**ESP32 side** (`esp32_rs485_responder.ino`):
```cpp
const int baudRates[] = {9600, 19200, 38400, 57600, 115200, 230400};
```

### Modifying Test Parameters

- Message count: `--messages` parameter or modify `self.message_count`
- Timeout: `--timeout` parameter or modify `self.timeout`
- Test message content: Modify `self.test_message` in Python code

## File Structure

```
baud_rate_sweep/
├── pc_baud_rate_sweep.py      # PC-side test program
├── esp32_rs485_responder.ino  # ESP32-S3 responder program
├── requirements.txt           # Python dependencies
├── README.md                  # This documentation
└── reports/                   # Generated test reports (auto-created)
    ├── rs485_baud_sweep_report_YYYYMMDD_HHMMSS.json
    └── rs485_baud_sweep_report_YYYYMMDD_HHMMSS.txt
```