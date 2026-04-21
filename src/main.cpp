#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// LCD (change to 20,4 or 16,4 if you bought larger)
LiquidCrystal_I2C lcd(0x27, 16, 2);  // most common address

#define BUZZER_PIN 4
#define TEST_BUTTON 0   // BOOT button on most S3 boards for quick testing

void setup() {
	Serial.begin(115200);
	pinMode(BUZZER_PIN, OUTPUT);
	pinMode(TEST_BUTTON, INPUT_PULLUP);
	
	// LCD init
	Wire.begin(8, 9);  // SDA, SCL
	lcd.init();
	lcd.backlight();
	lcd.clear();
	lcd.setCursor(0, 0);
	lcd.print("Smart Wallet");
	lcd.setCursor(0, 1);
	lcd.print("Ready - N16R8");
	
	Serial.println("\n=== Smart Wallet ESP32-S3 N16R8 Ready ===");
	Serial.printf("PSRAM: %d bytes available\n", ESP.getFreePsram());
	
	// Quick test beep
	digitalWrite(BUZZER_PIN, HIGH);
	delay(200);
	digitalWrite(BUZZER_PIN, LOW);
}

void loop() {
	if (digitalRead(TEST_BUTTON) == LOW) {  // simulate high-risk transaction
		lcd.clear();
		lcd.setCursor(0, 0);
		lcd.print("HIGH RISK!");
		lcd.setCursor(0, 1);
		lcd.print("Overspending");
		
		// Buzzer alert (meets FR2)
		
		for (int i = 0; i < 5; i++) {
			digitalWrite(BUZZER_PIN, HIGH);
			delay(100);
			digitalWrite(BUZZER_PIN, LOW);
			delay(100);
		}
		
		delay(2000);
		lcd.clear();
		lcd.print("Smart Wallet");
		lcd.setCursor(0, 1);
		lcd.print("Ready - N16R8");
	}
	delay(50);
}