/*
 * RS485 Data Integrity Test - ESP32-S3 Side
 *
 * This program echoes back all received data for testing RS485 adapter integrity
 * Connects to SP3485EN adapter via TTL (RX/TX)
 *
 * Hardware Setup:
 * - ESP32-S3-Zero RX/TX connected to RS485 adapter TTL side
 * - RS485 adapter A+/B- connected to PC via USB-RS485 adapter
 *
 * Configuration:
 * - Baud Rate: 9600 bps
 * - 8 data bits, No parity, 1 stop bit (8N1)
 */

#define BAUD_RATE 9600
#define SERIAL_CONFIG SERIAL_8N1

// ESP32-S3-Zero default pins for UART
#define RXD2 44  // GPIO44 (U0RXD) - adjust based on your board
#define TXD2 43  // GPIO43 (U0TXD) - adjust based on your board

// Buffer for data
#define BUFFER_SIZE 1024
uint8_t buffer[BUFFER_SIZE];

// Statistics
unsigned long totalBytesReceived = 0;
unsigned long totalBytesSent = 0;
unsigned long testStartTime = 0;
bool testActive = false;

void setup() {
  // Initialize Serial for debugging (USB)
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n===============================================");
  Serial.println("RS485 Data Integrity Test - ESP32-S3");
  Serial.println("===============================================");
  Serial.println("Waiting for data on Serial1...");
  Serial.printf("UART RX Pin: GPIO%d\n", RXD2);
  Serial.printf("UART TX Pin: GPIO%d\n", TXD2);
  Serial.printf("Baud Rate: %d bps\n", BAUD_RATE);
  Serial.println("===============================================\n");

  // Initialize Serial1 for RS485 communication (TTL side)
  Serial1.begin(BAUD_RATE, SERIAL_CONFIG, RXD2, TXD2);

  // Flush any existing data
  while (Serial1.available()) {
    Serial1.read();
  }

  totalBytesReceived = 0;
  totalBytesSent = 0;
  testActive = false;
}

void loop() {
  // Check if data is available
  if (Serial1.available()) {
    // Start test timing on first byte
    if (!testActive) {
      testActive = true;
      testStartTime = millis();
      totalBytesReceived = 0;
      totalBytesSent = 0;
      Serial.println("Test started - receiving data...");
    }

    // Read available bytes into buffer
    size_t bytesAvailable = Serial1.available();
    size_t bytesToRead = min(bytesAvailable, BUFFER_SIZE);
    size_t bytesRead = Serial1.readBytes(buffer, bytesToRead);

    // Echo back immediately
    if (bytesRead > 0) {
      size_t bytesWritten = Serial1.write(buffer, bytesRead);
      Serial1.flush();  // Ensure data is sent immediately

      totalBytesReceived += bytesRead;
      totalBytesSent += bytesWritten;

      // Debug output
      Serial.printf("RX: %lu bytes | TX: %lu bytes | Total: %lu/%lu\n",
                    bytesRead, bytesWritten, totalBytesReceived, totalBytesSent);

      // Check for write errors
      if (bytesWritten != bytesRead) {
        Serial.printf("WARNING: Write mismatch! Read %d, Wrote %d\n",
                      bytesRead, bytesWritten);
      }
    }
  }

  // Check for test completion (no data for 2 seconds)
  if (testActive && (millis() - testStartTime > 2000)) {
    if (Serial1.available() == 0) {
      unsigned long testDuration = millis() - testStartTime;

      Serial.println("\n===============================================");
      Serial.println("Test Completed");
      Serial.println("===============================================");
      Serial.printf("Total Bytes Received: %lu\n", totalBytesReceived);
      Serial.printf("Total Bytes Sent:     %lu\n", totalBytesSent);
      Serial.printf("Test Duration:        %lu ms\n", testDuration);
      Serial.printf("Throughput:           %.2f bytes/sec\n",
                    (float)totalBytesReceived / (testDuration / 1000.0));
      Serial.println("===============================================\n");
      Serial.println("Ready for next test...\n");

      testActive = false;
    }
  }

  // Small delay to prevent watchdog issues
  delay(1);
}
