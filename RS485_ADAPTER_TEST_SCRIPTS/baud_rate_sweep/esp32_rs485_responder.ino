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

// Baud rate detection
const int baudRates[] = {9600, 19200, 38400, 57600, 115200};
const int numBaudRates = sizeof(baudRates) / sizeof(baudRates[0]);
int currentBaudIndex = 0;
unsigned long lastBaudChangeTime = 0;
bool baudDetected = false;
int detectedBaud = 9600;

void setup() {
  // Initialize built-in LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize USB Serial for debugging
  Serial.begin(115200);
  delay(1000);

  Serial.println("RS485 Responder Starting...");
  Serial.println("ESP32-S3-Zero RS485 Baud Rate Sweep Test Responder");
  Serial.println("Waiting for messages from PC...");

  // Start with first baud rate
  startRS485Communication(baudRates[currentBaudIndex]);

  // Blink LED to indicate startup
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }
}

void loop() {
  // Handle LED blinking (indicates activity)
  handleLEDIndication();

  // Check for baud rate changes if no valid messages received
  if (!baudDetected) {
    checkBaudRateDetection();
  }

  // Read and process incoming messages
  readSerialData();

  // Process complete messages
  if (messageReady) {
    processMessage();
    messageReady = false;
  }

  // Watchdog - reset baud detection if no messages for too long
  if (millis() - lastMessageTime > 10000 && baudDetected) {
    Serial.println("No messages for 10 seconds, resetting baud detection");
    baudDetected = false;
    currentBaudIndex = 0;
    startRS485Communication(baudRates[currentBaudIndex]);
  }
}

void startRS485Communication(int baudRate) {
  rs485Serial.end();
  delay(100);

  // Use pins 17 (TX) and 18 (RX) for UART1
  rs485Serial.begin(baudRate, SERIAL_8N1, 18, 17);
  rs485Serial.setTimeout(100);

  Serial.print("Started RS485 at ");
  Serial.print(baudRate);
  Serial.println(" bps");

  lastBaudChangeTime = millis();
}

void checkBaudRateDetection() {
  // Try each baud rate for 3 seconds
  if (millis() - lastBaudChangeTime > 3000) {
    currentBaudIndex = (currentBaudIndex + 1) % numBaudRates;
    startRS485Communication(baudRates[currentBaudIndex]);
    Serial.print("Trying baud rate: ");
    Serial.println(baudRates[currentBaudIndex]);
  }
}

void readSerialData() {
  while (rs485Serial.available() && !messageReady) {
    char incomingByte = rs485Serial.read();

    if (incomingByte == '\n' || incomingByte == '\r') {
      if (currentMessage.length() > 0) {
        messageReady = true;
        break;
      }
    } else if (incomingByte >= 32 && incomingByte <= 126) {  // Printable ASCII
      if (currentMessage.length() < MAX_MESSAGE_LENGTH) {
        currentMessage += incomingByte;
      }
    }
  }
}

void processMessage() {
  if (currentMessage.length() == 0) {
    return;
  }

  Serial.print("Received: ");
  Serial.println(currentMessage);

  // Check if this looks like a test message
  if (currentMessage.startsWith("RS485_TEST_MESSAGE_")) {
    if (!baudDetected) {
      baudDetected = true;
      detectedBaud = baudRates[currentBaudIndex];
      Serial.print("Baud rate detected: ");
      Serial.println(detectedBaud);

      // Blink LED rapidly to indicate detection
      for (int i = 0; i < 10; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(50);
        digitalWrite(LED_PIN, LOW);
        delay(50);
      }
    }

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
    Serial.println("Not a test message - ignoring");
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

  if (baudDetected) {
    // Slow heartbeat when baud rate detected and operational
    if (currentTime - ledBlinkTime > 1000) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState ? HIGH : LOW);
      ledBlinkTime = currentTime;
    }
  } else {
    // Fast blink when searching for baud rate
    if (currentTime - ledBlinkTime > 200) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState ? HIGH : LOW);
      ledBlinkTime = currentTime;
    }
  }
}

void printStatus() {
  Serial.println("\n--- Status ---");
  Serial.print("Detected Baud: ");
  if (baudDetected) {
    Serial.print(detectedBaud);
    Serial.println(" bps");
  } else {
    Serial.print("Searching... (trying ");
    Serial.print(baudRates[currentBaudIndex]);
    Serial.println(" bps)");
  }
  Serial.print("Messages processed: ");
  Serial.println(messageCount);
  Serial.print("Uptime: ");
  Serial.print(millis() / 1000);
  Serial.println(" seconds");
  Serial.println("-------------\n");
}

// Print status every 30 seconds
void loop() {
  static unsigned long lastStatusTime = 0;

  // Handle LED blinking (indicates activity)
  handleLEDIndication();

  // Check for baud rate changes if no valid messages received
  if (!baudDetected) {
    checkBaudRateDetection();
  }

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

  // Watchdog - reset baud detection if no messages for too long
  if (millis() - lastMessageTime > 10000 && baudDetected) {
    Serial.println("No messages for 10 seconds, resetting baud detection");
    baudDetected = false;
    currentBaudIndex = 0;
    startRS485Communication(baudRates[currentBaudIndex]);
  }
}