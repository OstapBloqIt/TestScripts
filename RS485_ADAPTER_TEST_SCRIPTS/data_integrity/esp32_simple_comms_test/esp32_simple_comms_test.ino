/*
 * Simple RS485 Communication Test - ESP32-S3
 * Receives messages and responds with "ACK: " + original message
 */

#define BAUD_RATE 9600
#define RXD2 18  // GPIO18 (U1RXD)
#define TXD2 17  // GPIO17 (U1TXD)

HardwareSerial rs485Serial(1);  // Use UART1

String incomingMessage = "";
bool messageComplete = false;

void setup() {
  // Initialize USB Serial for debugging
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=== Simple RS485 Communication Test ===");
  Serial.println("Waiting for messages on RS485...");
  Serial.printf("RX: GPIO%d, TX: GPIO%d, Baud: %d\n\n", RXD2, TXD2, BAUD_RATE);

  // Initialize RS485 Serial
  rs485Serial.begin(BAUD_RATE, SERIAL_8N1, RXD2, TXD2);

  Serial.println("Ready!");
}

void loop() {
  // Read incoming data
  while (rs485Serial.available() > 0) {
    char inChar = (char)rs485Serial.read();

    // Add character to message
    incomingMessage += inChar;

    // Check for newline (message terminator)
    if (inChar == '\n') {
      messageComplete = true;
      break;
    }
  }

  // Process complete message
  if (messageComplete) {
    // Remove newline/carriage return
    incomingMessage.trim();

    // Display received message on USB Serial
    Serial.println("===============================================");
    Serial.print("RECEIVED: ");
    Serial.println(incomingMessage);

    // Create ACK response
    String response = "ACK: " + incomingMessage;

    // Small delay before transmitting
    delayMicroseconds(100);

    // Send ACK response
    rs485Serial.println(response);
    rs485Serial.flush();

    Serial.print("SENT: ");
    Serial.println(response);
    Serial.println("===============================================\n");

    // Reset for next message
    incomingMessage = "";
    messageComplete = false;
  }

  delay(1);
}
