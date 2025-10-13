/*
 * RS485 Simple Listener - ESP32-S3-Zero
 * Listens for any messages on RS485 at 9600 baud and prints them to Serial
 *
 * Hardware Setup:
 * - ESP32-S3-Zero board
 * - TX/RX TTL signals connected to RS485 adapter (TX=GPIO17, RX=GPIO18)
 * - A+/B- differential signals to PC via RS485-USB adapter
 *
 * This is a simple debug tool to verify RS485 communication
 */

#include <HardwareSerial.h>

// Configuration
#define LED_PIN 2  // Built-in LED on ESP32-S3-Zero
#define BAUD_RATE 9600

// Serial communication
HardwareSerial rs485Serial(1);  // Use UART1

// Status
unsigned long messageCount = 0;
unsigned long lastActivityTime = 0;

void setup() {
  // Initialize built-in LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize USB Serial for debugging
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n===========================================");
  Serial.println("RS485 Simple Listener");
  Serial.println("ESP32-S3-Zero @ 9600 baud");
  Serial.println("===========================================");

  // Initialize RS485 serial on UART1
  // Pins: 17 (TX), 18 (RX)
  rs485Serial.begin(BAUD_RATE, SERIAL_8N1, 18, 17);

  Serial.print("Listening on RS485 at ");
  Serial.print(BAUD_RATE);
  Serial.println(" bps");
  Serial.println("Pins: TX=GPIO17, RX=GPIO18");
  Serial.println("Waiting for messages...\n");

  // Startup LED sequence
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }

  lastActivityTime = millis();
}

void loop() {
  static String incomingMessage = "";
  static unsigned long lastHeartbeat = 0;
  static bool ledState = false;

  // Heartbeat LED (blink every second to show we're alive)
  if (millis() - lastHeartbeat > 1000) {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    lastHeartbeat = millis();
  }

  // Check for incoming data
  while (rs485Serial.available()) {
    char incomingChar = rs485Serial.read();

    lastActivityTime = millis();

    // Print raw byte value for debugging
    Serial.print("0x");
    Serial.print(incomingChar, HEX);
    Serial.print(" ");

    // Check for end of message
    if (incomingChar == '\n' || incomingChar == '\r') {
      if (incomingMessage.length() > 0) {
        // Message complete
        messageCount++;

        Serial.println(); // New line
        Serial.print("[MSG #");
        Serial.print(messageCount);
        Serial.print("] ");
        Serial.println(incomingMessage);
        Serial.println();

        // Flash LED on message received
        digitalWrite(LED_PIN, HIGH);
        delay(50);
        digitalWrite(LED_PIN, LOW);

        // Clear message buffer
        incomingMessage = "";
      }
    } else if (incomingChar >= 32 && incomingChar <= 126) {
      // Printable ASCII character
      incomingMessage += incomingChar;
    } else {
      // Non-printable character - just show in hex output above
    }
  }

  // Print periodic status
  static unsigned long lastStatus = 0;
  if (millis() - lastStatus > 30000) {
    Serial.println("\n--- Status ---");
    Serial.print("Messages received: ");
    Serial.println(messageCount);
    Serial.print("Last activity: ");
    Serial.print((millis() - lastActivityTime) / 1000);
    Serial.println(" seconds ago");
    Serial.print("Uptime: ");
    Serial.print(millis() / 1000);
    Serial.println(" seconds");
    Serial.println("-------------\n");
    lastStatus = millis();
  }
}
