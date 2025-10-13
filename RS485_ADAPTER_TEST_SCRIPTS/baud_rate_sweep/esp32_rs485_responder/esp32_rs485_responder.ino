/*
 * RS485 Adapter Baud Rate Sweep Test - ESP32-S3-Zero Side
 * Responds to test messages from PC via RS485 connection
 *
 * Hardware Setup:
 * - ESP32-S3-Zero board
 * - TX/RX TTL signals connected to RS485 adapter
 * - A+/B- differential signals to PC via RS485-USB adapter
 *
 * The program automatically detects baud rate and responds to test messages
 */

#include <HardwareSerial.h>

// Configuration
#define SERIAL_BUFFER_SIZE 256
#define LED_PIN 2  // Built-in LED on ESP32-S3-Zero
#define MAX_MESSAGE_LENGTH 128

// Serial communication
HardwareSerial rs485Serial(1);  // Use UART1

// Status variables
unsigned long messageCount = 0;
unsigned long lastMessageTime = 0;
unsigned long ledBlinkTime = 0;
bool ledState = false;
String currentMessage = "";
bool messageReady = false;

// Baud rate management
const int baudRates[] = {9600, 19200, 38400, 57600, 115200};
const int numBaudRates = sizeof(baudRates) / sizeof(baudRates[0]);
int currentBaudIndex = 0;
int currentBaud = 9600;

void setup() {
  // Initialize built-in LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize USB Serial for debugging
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n===========================================");
  Serial.println("RS485 Responder Starting...");
  Serial.println("ESP32-S3-Zero RS485 Baud Rate Sweep Test Responder");
  Serial.println("===========================================");
  Serial.println("Waiting for messages from PC...");
  Serial.print("Supported baud rates: ");
  for (int i = 0; i < numBaudRates; i++) {
    Serial.print(baudRates[i]);
    if (i < numBaudRates - 1) Serial.print(", ");
  }
  Serial.println();

  // Start with first baud rate
  startRS485Communication(baudRates[currentBaudIndex]);

  // Blink LED to indicate startup
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }

  Serial.println("Ready! Listening for test messages...");
}

void loop() {
  static unsigned long lastStatusTime = 0;

  // Handle LED blinking (indicates activity)
  handleLEDIndication();

  // Read and process incoming messages
  readSerialData();

  // Process complete messages
  if (messageReady) {
    processMessage();
    messageReady = false;
  }

  // Print status periodically
  if (millis() - lastStatusTime > 30000) {
    printStatus();
    lastStatusTime = millis();
  }
}

void startRS485Communication(int baudRate) {
  rs485Serial.end();
  delay(100);

  // Use pins 17 (TX) and 18 (RX) for UART1
  rs485Serial.begin(baudRate, SERIAL_8N1, 18, 17);
  rs485Serial.setTimeout(100);

  // Clear any garbage from buffer after baud rate change
  delay(50);
  while (rs485Serial.available()) {
    rs485Serial.read();
  }

  // Clear message buffer
  currentMessage = "";
  messageReady = false;

  currentBaud = baudRate;

  Serial.print("Started RS485 at ");
  Serial.print(baudRate);
  Serial.println(" bps");
}

void changeBaudRate(int newBaudRate) {
  // Find the index of the new baud rate
  for (int i = 0; i < numBaudRates; i++) {
    if (baudRates[i] == newBaudRate) {
      currentBaudIndex = i;
      startRS485Communication(newBaudRate);
      Serial.print("Changed to baud rate: ");
      Serial.println(newBaudRate);
      return;
    }
  }
  Serial.print("ERROR: Invalid baud rate requested: ");
  Serial.println(newBaudRate);
}

void readSerialData() {
  static unsigned long lastDebugTime = 0;
  static int bytesReceived = 0;

  while (rs485Serial.available() && !messageReady) {
    char incomingByte = rs485Serial.read();
    bytesReceived++;

    // Debug: Print raw bytes periodically
    if (millis() - lastDebugTime > 1000 && bytesReceived > 0) {
      Serial.print("DEBUG: Received ");
      Serial.print(bytesReceived);
      Serial.print(" bytes in last second at ");
      Serial.print(baudRates[currentBaudIndex]);
      Serial.println(" bps");
      bytesReceived = 0;
      lastDebugTime = millis();
    }

    if (incomingByte == '\n' || incomingByte == '\r') {
      if (currentMessage.length() > 0) {
        messageReady = true;
        break;
      }
    } else if (incomingByte >= 32 && incomingByte <= 126) {  // Printable ASCII
      if (currentMessage.length() < MAX_MESSAGE_LENGTH) {
        currentMessage += incomingByte;
      }
    } else {
      // Debug: Log non-printable characters
      Serial.print("DEBUG: Non-printable byte: 0x");
      Serial.println(incomingByte, HEX);
    }
  }
}

void processMessage() {
  if (currentMessage.length() == 0) {
    return;
  }

  Serial.print("Received: ");
  Serial.println(currentMessage);

  // Check for baud rate change command
  if (currentMessage.startsWith("CHANGE_BAUD_")) {
    // Format: CHANGE_BAUD_xxxxx (e.g., CHANGE_BAUD_19200)
    String baudStr = currentMessage.substring(12);
    int newBaud = baudStr.toInt();

    if (newBaud > 0) {
      // Send acknowledgment at current baud rate
      rs485Serial.println("ACK_BAUD_CHANGE");
      rs485Serial.flush();
      delay(100);

      // Change to new baud rate
      changeBaudRate(newBaud);
    } else {
      Serial.println("Invalid baud rate in command");
    }
  }
  // Check if this looks like a test message
  else if (currentMessage.startsWith("RS485_TEST_MESSAGE_")) {
    // Validate message format
    if (validateMessage(currentMessage)) {
      // Send ACK response
      String response = "ACK_" + currentMessage;
      rs485Serial.println(response);

      messageCount++;
      lastMessageTime = millis();

      Serial.print("Sent ACK (");
      Serial.print(messageCount);
      Serial.print("): ");
      Serial.println(response);

      // Quick LED blink for successful message
      digitalWrite(LED_PIN, HIGH);
      delay(10);
      digitalWrite(LED_PIN, LOW);
    } else {
      Serial.println("Invalid message format - no response sent");
    }
  } else {
    Serial.println("Unknown message type - ignoring");
  }

  // Clear the message buffer
  currentMessage = "";
}

bool validateMessage(const String& message) {
  // Expected format: RS485_TEST_MESSAGE_NNNN_XXXXXXXX
  // Where NNNN is 4-digit sequence number and XXXXXXXX is 8-char checksum

  if (message.length() < 32) {  // Minimum expected length
    return false;
  }

  // Check prefix
  if (!message.startsWith("RS485_TEST_MESSAGE_")) {
    return false;
  }

  // Find the last underscore (before checksum)
  int lastUnderscore = message.lastIndexOf('_');
  if (lastUnderscore == -1 || lastUnderscore < 19) {
    return false;
  }

  // Check if we have a checksum part
  String checksumPart = message.substring(lastUnderscore + 1);
  if (checksumPart.length() != 8) {
    return false;
  }

  // Validate checksum contains only hex characters
  for (int i = 0; i < checksumPart.length(); i++) {
    char c = checksumPart.charAt(i);
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) {
      return false;
    }
  }

  return true;
}

void handleLEDIndication() {
  unsigned long currentTime = millis();

  // Slow heartbeat to show device is alive
  if (currentTime - ledBlinkTime > 1000) {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    ledBlinkTime = currentTime;
  }
}

void printStatus() {
  Serial.println("\n--- Status ---");
  Serial.print("Current Baud Rate: ");
  Serial.print(currentBaud);
  Serial.println(" bps");
  Serial.print("Messages processed: ");
  Serial.println(messageCount);
  Serial.print("Uptime: ");
  Serial.print(millis() / 1000);
  Serial.println(" seconds");
  Serial.println("-------------\n");
}

