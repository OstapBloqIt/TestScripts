/*
 * RS485 Data Integrity Test - ESP32-S3 Side
 *
 * NUCLEAR MODE: Buffer all incoming data, wait for silence, then echo all back
 * AUTO BAUD NEGOTIATION: Starts at 9600, can switch to any baud rate on command
 *
 * This program echoes back all received data for testing RS485 adapter integrity
 * Connects to SP3485EN adapter via TTL (RX/TX)
 *
 * Hardware Setup:
 * - ESP32-S3-Zero RX/TX connected to RS485 adapter TTL side
 * - RS485 adapter A+/B- connected to PC via USB-RS485 adapter
 *
 * Protocol:
 * - Starts at 9600 baud
 * - PC sends: "BAUD:xxxxx\n" to change baud rate
 * - ESP32 responds: "ACK:xxxxx\n" and switches
 * - Both sides switch to new baud rate
 * - PC sends: "TEST\n" to verify
 * - ESP32 responds: "OK\n" if successful
 *
 * Configuration:
 * - Initial Baud Rate: 9600 bps (auto-negotiates from there)
 * - 8 data bits, No parity, 1 stop bit (8N1)
 */

#define INITIAL_BAUD_RATE 9600  // Always starts at 9600
#define SERIAL_CONFIG SERIAL_8N1

// ESP32-S3-Zero UART1 pins
#define RXD2 18  // GPIO18 (U1RXD)
#define TXD2 17  // GPIO17 (U1TXD)

// Buffer for data
#define BUFFER_SIZE 1024
uint8_t buffer[BUFFER_SIZE];

// Statistics
unsigned long totalBytesReceived = 0;
unsigned long totalBytesSent = 0;
unsigned long testStartTime = 0;
bool testActive = false;
unsigned long currentBaudRate = INITIAL_BAUD_RATE;

HardwareSerial rs485Serial(1);  // Use UART1

String commandBuffer = "";  // Buffer for commands

void setup() {
  // Initialize Serial for debugging (USB)
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n===============================================");
  Serial.println("RS485 Data Integrity Test - ESP32-S3");
  Serial.println("AUTO BAUD NEGOTIATION ENABLED");
  Serial.println("===============================================");
  Serial.println("Waiting for data on rs485Serial...");
  Serial.printf("UART RX Pin: GPIO%d\n", RXD2);
  Serial.printf("UART TX Pin: GPIO%d\n", TXD2);
  Serial.printf("Initial Baud Rate: %lu bps\n", currentBaudRate);
  Serial.println("===============================================\n");

  // Initialize rs485Serial for RS485 communication (TTL side)
  rs485Serial.begin(currentBaudRate, SERIAL_CONFIG, RXD2, TXD2);

  // Flush any existing data
  while (rs485Serial.available()) {
    rs485Serial.read();
  }

  totalBytesReceived = 0;
  totalBytesSent = 0;
  testActive = false;
}

bool changeBaudRate(unsigned long newBaud) {
  Serial.printf("\n>>> Changing baud rate to %lu...\n", newBaud);

  rs485Serial.end();
  delay(100);

  rs485Serial.begin(newBaud, SERIAL_CONFIG, RXD2, TXD2);
  currentBaudRate = newBaud;

  // Flush buffer
  while (rs485Serial.available()) {
    rs485Serial.read();
  }

  Serial.printf(">>> Baud rate changed to %lu bps\n", currentBaudRate);
  return true;
}

bool processCommand(String cmd) {
  cmd.trim();

  Serial.printf("Command received: '%s'\n", cmd.c_str());

  // Check for baud rate change command: "BAUD:xxxxx"
  if (cmd.startsWith("BAUD:")) {
    unsigned long newBaud = cmd.substring(5).toInt();

    if (newBaud >= 9600 && newBaud <= 115200) {
      // Send ACK before switching
      delay(50);
      String ack = "ACK:" + String(newBaud) + "\n";
      rs485Serial.print(ack);
      rs485Serial.flush();

      Serial.printf("Sent ACK, switching to %lu baud...\n", newBaud);

      // Wait for ACK to be transmitted
      delay(100);

      // Change baud rate
      changeBaudRate(newBaud);

      return true;
    } else {
      Serial.printf("Invalid baud rate: %lu\n", newBaud);
      return false;
    }
  }
  // Check for test verification: "TEST"
  else if (cmd == "TEST") {
    delay(50);
    rs485Serial.println("OK");
    rs485Serial.flush();
    Serial.println("Sent OK in response to TEST");
    return true;
  }

  return false;
}

void loop() {
  // Check for incoming data
  if (rs485Serial.available() > 0) {
    char inChar = rs485Serial.read();

    // If we're in test mode, just buffer everything
    if (testActive) {
      buffer[totalBytesReceived++] = inChar;
      testStartTime = millis();
      Serial.printf("Buffering... Total received: %lu bytes\r", totalBytesReceived);
    }
    // Not in test mode - check for commands
    else {
      // Check if this is a command (text with newline) or data test
      if (inChar == '\n') {
        // Process command
        if (commandBuffer.length() > 0) {
          bool cmdProcessed = processCommand(commandBuffer);
          commandBuffer = "";

          // If command wasn't recognized, it might be data
          if (!cmdProcessed && commandBuffer.length() > 0) {
            // Start data test mode
            testActive = true;
            testStartTime = millis();
            totalBytesReceived = 0;
            totalBytesSent = 0;
            Serial.println("Test started - NUCLEAR MODE!");

            // Add buffered data
            for (int i = 0; i < commandBuffer.length(); i++) {
              buffer[totalBytesReceived++] = commandBuffer[i];
            }
            buffer[totalBytesReceived++] = '\n';
            commandBuffer = "";
          }
        }
      } else if (inChar >= 32 && inChar < 127) {
        // Printable ASCII - likely a command
        commandBuffer += inChar;

        // If command buffer gets too long, assume it's data, not command
        if (commandBuffer.length() > 20) {
          // This is data, not a command - switch to data mode
          testActive = true;
          testStartTime = millis();
          totalBytesReceived = 0;
          totalBytesSent = 0;
          Serial.println("Test started - NUCLEAR MODE!");

          // Add command buffer to data buffer
          for (int i = 0; i < commandBuffer.length(); i++) {
            buffer[totalBytesReceived++] = commandBuffer[i];
          }
          commandBuffer = "";
        }
      } else {
        // Non-printable character - this is data, not a command
        testActive = true;
        testStartTime = millis();
        totalBytesReceived = 0;
        totalBytesSent = 0;
        Serial.println("Test started - NUCLEAR MODE!");

        // Add any buffered command as data
        for (int i = 0; i < commandBuffer.length(); i++) {
          buffer[totalBytesReceived++] = commandBuffer[i];
        }
        commandBuffer = "";

        // Add this byte to data buffer
        buffer[totalBytesReceived++] = inChar;

        Serial.printf("Buffering... Total received: %lu bytes\r", totalBytesReceived);
      }
    }
  }

  // In data test mode
  if (testActive) {
    // Continue reading data
    while (rs485Serial.available() > 0 && totalBytesReceived < BUFFER_SIZE) {
      buffer[totalBytesReceived] = rs485Serial.read();
      totalBytesReceived++;
      testStartTime = millis();  // Update last activity time
    }

    // Check if transmission has stopped (no new data for 500ms)
    if (totalBytesReceived > 0 && (millis() - testStartTime > 500)) {
      // PC has finished transmitting - now echo everything back!
      Serial.println("\n\n>>> PC transmission complete! Echoing all data back...");

      // Additional delay to ensure PC's RS485 adapter has switched to RX mode
      delay(100);

      // Send everything back at once
      size_t bytesWritten = rs485Serial.write(buffer, totalBytesReceived);
      rs485Serial.flush();

      totalBytesSent = bytesWritten;

      Serial.println("===============================================");
      Serial.println("Echo Transmission Complete!");
      Serial.println("===============================================");
      Serial.printf("Total Bytes Received: %lu\n", totalBytesReceived);
      Serial.printf("Total Bytes Sent:     %lu\n", totalBytesSent);
      Serial.println("===============================================\n");

      if (bytesWritten != totalBytesReceived) {
        Serial.printf("WARNING: Mismatch! Received %lu, Sent %lu\n",
                      totalBytesReceived, bytesWritten);
      }

      // Reset for next test
      testActive = false;
      totalBytesReceived = 0;
      totalBytesSent = 0;

      Serial.println("Ready for next test...\n");
    }
  }

  delay(1);
}
