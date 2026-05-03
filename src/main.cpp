#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Adafruit_NeoPixel.h>

// LCD (change to 20,4 or 16,4 if you bought larger)
LiquidCrystal_I2C lcd(0x27, 16, 2);  // most common address

#define BUZZER_PIN 4
#define TEST_BUTTON 0   // BOOT button on most S3 boards for quick testing

#define USE_ONBOARD_RGB_LED 1
#define ONBOARD_RGB_PIN 48  // common ESP32-S3 DevKit onboard RGB LED pin
#define ONBOARD_RGB_COUNT 1

// Use these later when you have current-limiting resistors for external LEDs.
#define RED_LED_PIN 5
#define GREEN_LED_PIN 6

#if USE_ONBOARD_RGB_LED
Adafruit_NeoPixel onboardLed(ONBOARD_RGB_COUNT, ONBOARD_RGB_PIN, NEO_GRB + NEO_KHZ800);
#endif

bool lastButtonPressed = false;

void setLedState(bool redOn, bool greenOn) {
#if USE_ONBOARD_RGB_LED
	uint32_t color = onboardLed.Color(redOn ? 20 : 0, greenOn ? 20 : 0, 0);
	onboardLed.setPixelColor(0, color);
	onboardLed.show();
#else
	digitalWrite(RED_LED_PIN, redOn ? HIGH : LOW);
	digitalWrite(GREEN_LED_PIN, greenOn ? HIGH : LOW);
#endif
}

void showReady() {
	setLedState(false, true);
	lcd.clear();
	lcd.setCursor(0, 0);
	lcd.print("Smart Wallet");
	lcd.setCursor(0, 1);
	lcd.print("Ready - N16R8");
	Serial.println("STATE: READY");
}

void showLowRisk() {
	setLedState(false, true);
	lcd.clear();
	lcd.setCursor(0, 0);
	lcd.print("Risk: LOW");
	lcd.setCursor(0, 1);
	lcd.print("Transaction OK");
	Serial.println("STATE: LOW_RISK");
}

void playHighRiskAlert() {
	for (int i = 0; i < 5; i++) {
		digitalWrite(BUZZER_PIN, HIGH);
		setLedState(true, false);
		delay(100);
		digitalWrite(BUZZER_PIN, LOW);
		setLedState(false, false);
		delay(100);
	}
}

void showHighRisk() {
	lcd.clear();
	lcd.setCursor(0, 0);
	lcd.print("HIGH RISK!");
	lcd.setCursor(0, 1);
	lcd.print("Overspending");
	Serial.println("STATE: HIGH_RISK");
	playHighRiskAlert();
	setLedState(true, false);
}

void handleSerialCommand(char command) {
	if (command >= 'a' && command <= 'z') {
		command = command - 'a' + 'A';
	}

	switch (command) {
		case 'H':
			showHighRisk();
			break;
		case 'L':
			showLowRisk();
			break;
		case 'R':
			showReady();
			break;
		default:
			break;
	}
}

void setup() {
	Serial.begin(115200);
	pinMode(BUZZER_PIN, OUTPUT);
#if USE_ONBOARD_RGB_LED
	onboardLed.begin();
	onboardLed.setBrightness(40);
	onboardLed.show();
#else
	pinMode(RED_LED_PIN, OUTPUT);
	pinMode(GREEN_LED_PIN, OUTPUT);
#endif
	pinMode(TEST_BUTTON, INPUT_PULLUP);
	
	// LCD init
	Wire.begin(8, 9);  // SDA, SCL
	lcd.init();
	lcd.backlight();
	showReady();
	
	Serial.println("\n=== Smart Wallet ESP32-S3 N16R8 Ready ===");
	Serial.printf("PSRAM: %d bytes available\n", ESP.getFreePsram());
	Serial.println("Commands: H = high risk, L = low risk, R = ready");
	
	// Quick test beep
	digitalWrite(BUZZER_PIN, HIGH);
	delay(200);
	digitalWrite(BUZZER_PIN, LOW);
}

void loop() {
	while (Serial.available() > 0) {
		handleSerialCommand(Serial.read());
	}

	bool buttonPressed = digitalRead(TEST_BUTTON) == LOW;
	if (buttonPressed && !lastButtonPressed) {  // simulate high-risk transaction
		showHighRisk();
		delay(2000);
		showReady();
	}
	lastButtonPressed = buttonPressed;

	delay(50);
}
