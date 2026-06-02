#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Component-test firmware for the Smart Wallet hardware.
//
// Wiring assumed for this test:
// - LCD SDA -> GPIO8, LCD SCL -> GPIO9
// - Buzzer -> GPIO4
// - Red LED -> GPIO5 through a resistor
// - Yellow LED -> GPIO6 through a resistor
// - Green LED -> GPIO7 through a resistor
// - Red button -> GPIO10 to GND
// - Yellow button -> GPIO11 to GND
// - Green button -> GPIO12 to GND
//
// Buttons use INPUT_PULLUP, so a pressed button reads LOW.
// Change the pin numbers below if your wiring is different.

#define LCD_SDA_PIN 8
#define LCD_SCL_PIN 9
#define LCD_ADDRESS 0x27
#define LCD_COLUMNS 16
#define LCD_ROWS 2

#define BUZZER_PIN 4

#define RED_LED_PIN 42
#define YELLOW_LED_PIN 41
#define GREEN_LED_PIN 40

#define RED_BUTTON_PIN 10
#define YELLOW_BUTTON_PIN 11
#define GREEN_BUTTON_PIN 12

#define DEBOUNCE_MS 35

LiquidCrystal_I2C lcd(LCD_ADDRESS, LCD_COLUMNS, LCD_ROWS);

struct TestChannel {
	const char *name;
	const char *lcdLine;
	uint8_t buttonPin;
	uint8_t ledPin;
	uint16_t beepOnMs;
	uint16_t beepOffMs;
	uint8_t beepCount;
	bool stablePressed;
	bool lastRawPressed;
	unsigned long lastRawChangeMs;
};

TestChannel channels[] = {
	{"RED", "HIGH ALERT", RED_BUTTON_PIN, RED_LED_PIN, 120, 80, 4, false, false, 0},
	{"YELLOW", "WARNING", YELLOW_BUTTON_PIN, YELLOW_LED_PIN, 90, 80, 2, false, false, 0},
	{"GREEN", "NORMAL OK", GREEN_BUTTON_PIN, GREEN_LED_PIN, 60, 60, 1, false, false, 0},
};

const size_t CHANNEL_COUNT = sizeof(channels) / sizeof(channels[0]);

void setAllLeds(bool redOn, bool yellowOn, bool greenOn) {
	digitalWrite(RED_LED_PIN, redOn ? HIGH : LOW);
	digitalWrite(YELLOW_LED_PIN, yellowOn ? HIGH : LOW);
	digitalWrite(GREEN_LED_PIN, greenOn ? HIGH : LOW);
}

void showMessage(const char *line1, const char *line2) {
	lcd.clear();
	lcd.setCursor(0, 0);
	lcd.print(line1);
	lcd.setCursor(0, 1);
	lcd.print(line2);
}

void beep(uint16_t onMs, uint16_t offMs, uint8_t count) {
	for (uint8_t i = 0; i < count; i++) {
		digitalWrite(BUZZER_PIN, HIGH);
		delay(onMs);
		digitalWrite(BUZZER_PIN, LOW);
		if (i + 1 < count) {
			delay(offMs);
		}
	}
}

void showReady() {
	setAllLeds(false, false, true);
	showMessage("Smart Wallet", "Ready");
	Serial.println("STATE: READY");
	Serial.println("Serial: H=high risk, L=low risk, W=warning, R=ready, A=test all, B=buzzer, 0=off");
}

void turnOffOutputs() {
	setAllLeds(false, false, false);
	digitalWrite(BUZZER_PIN, LOW);
	showMessage("Outputs Off", "Send A or press");
	Serial.println("STATE: OUTPUTS_OFF");
}

void runChannelTest(size_t index, const char *source) {
	if (index >= CHANNEL_COUNT) {
		return;
	}

	TestChannel &channel = channels[index];
	setAllLeds(false, false, false);
	digitalWrite(channel.ledPin, HIGH);

	char line1[17];
	snprintf(line1, sizeof(line1), "%s %s", channel.name, source);
	showMessage(line1, channel.lcdLine);

	Serial.print("TEST: ");
	Serial.print(channel.name);
	Serial.print(" from ");
	Serial.println(source);
	if (index == 0) {
		Serial.println("STATE: HIGH_RISK");
	} else if (index == 1) {
		Serial.println("STATE: WARNING");
	} else if (index == 2) {
		Serial.println("STATE: LOW_RISK");
	}

	beep(channel.beepOnMs, channel.beepOffMs, channel.beepCount);
}

void runAllLedTest() {
	Serial.println("TEST: ALL_LEDS");
	showMessage("LED Test", "Red");
	setAllLeds(true, false, false);
	beep(80, 50, 1);
	delay(500);

	showMessage("LED Test", "Yellow");
	setAllLeds(false, true, false);
	beep(80, 50, 1);
	delay(500);

	showMessage("LED Test", "Green");
	setAllLeds(false, false, true);
	beep(80, 50, 1);
	delay(500);

	showMessage("LED Test", "All On");
	setAllLeds(true, true, true);
	beep(100, 70, 2);
	delay(700);

	showReady();
}

void runBuzzerTest() {
	Serial.println("TEST: BUZZER");
	showMessage("Buzzer Test", "Beeping...");
	beep(100, 100, 3);
	showReady();
}

void handleSerialCommand(char command) {
	if (command >= 'a' && command <= 'z') {
		command = command - 'a' + 'A';
	}

	switch (command) {
		case '1':
		case 'H':
			runChannelTest(0, "SERIAL");
			break;
		case '2':
		case 'Y':
		case 'W':
			runChannelTest(1, "SERIAL");
			break;
		case '3':
		case 'G':
		case 'L':
			runChannelTest(2, "SERIAL");
			break;
		case 'R':
			showReady();
			break;
		case 'A':
		case 'T':
			runAllLedTest();
			break;
		case 'B':
			runBuzzerTest();
			break;
		case '0':
		case 'O':
			turnOffOutputs();
			break;
		default:
			break;
	}
}

void updateButtons() {
	unsigned long now = millis();

	for (size_t i = 0; i < CHANNEL_COUNT; i++) {
		TestChannel &channel = channels[i];
		bool rawPressed = digitalRead(channel.buttonPin) == LOW;

		if (rawPressed != channel.lastRawPressed) {
			channel.lastRawPressed = rawPressed;
			channel.lastRawChangeMs = now;
		}

		if ((now - channel.lastRawChangeMs) < DEBOUNCE_MS) {
			continue;
		}

		if (rawPressed != channel.stablePressed) {
			channel.stablePressed = rawPressed;
			if (channel.stablePressed) {
				runChannelTest(i, "BUTTON");
			}
		}
	}
}

void setup() {
	Serial.begin(115200);
	delay(300);

	pinMode(BUZZER_PIN, OUTPUT);
	pinMode(RED_LED_PIN, OUTPUT);
	pinMode(YELLOW_LED_PIN, OUTPUT);
	pinMode(GREEN_LED_PIN, OUTPUT);
	pinMode(RED_BUTTON_PIN, INPUT_PULLUP);
	pinMode(YELLOW_BUTTON_PIN, INPUT_PULLUP);
	pinMode(GREEN_BUTTON_PIN, INPUT_PULLUP);

	digitalWrite(BUZZER_PIN, LOW);
	setAllLeds(false, false, false);

	Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
	lcd.init();
	lcd.backlight();

	Serial.println();
	Serial.println("=== Smart Wallet Component Test ===");
	Serial.println("Buttons are active-low: connect each button pin to GND when pressed.");
	Serial.println("Use resistors in series with external LEDs.");

	showMessage("Booting Test", "LCD is working");
	beep(120, 80, 1);
	delay(700);
	runAllLedTest();
}

void loop() {
	while (Serial.available() > 0) {
		handleSerialCommand(Serial.read());
	}

	updateButtons();
	delay(5);
}
