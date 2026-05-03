# Smart Wallet Hardware Alert Module

This ESP32-S3 module displays the prediction result from the Smart Wallet backend.

- `H`: high overspending risk, show LCD warning, flash red onboard LED, beep buzzer
- `L`: low risk, show safe message, green onboard LED
- `R`: ready state

The BOOT button still simulates a high-risk transaction for offline testing.

## Current Wiring

| Part | ESP32-S3 Pin |
| --- | --- |
| Buzzer | GPIO4 |
| LCD SDA | GPIO8 |
| LCD SCL | GPIO9 |
| BOOT test button | GPIO0 |
| Onboard RGB LED | GPIO48 |

The sketch currently uses the onboard RGB LED. When external LEDs are used later,
add resistors first, then set `USE_ONBOARD_RGB_LED` to `0` in `src/main.cpp`.

## Manual Serial Test

Upload the firmware and open the PlatformIO serial monitor at `115200` baud.
Send one of these commands:

```text
H
L
R
```

## Backend Bridge Test

The bridge script calls the backend prediction endpoint and forwards the result
to the ESP32 over serial.

In a separate terminal, start the backend first:

```powershell
cd ..\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

From `hardware/`:

```powershell
python -m pip install -r tools\requirements.txt
python tools\serial_prediction_bridge.py --list-ports
python tools\serial_prediction_bridge.py --api-url http://127.0.0.1:8000 --email test.user@example.com --password SecurePass123! --port COM5
```

Replace `COM5` with the ESP32 port shown by `--list-ports`.
Opening the serial port can reset the ESP32-S3. The bridge waits for the board
to print its ready message before sending `H` or `L`, then keeps the port open
briefly so the LCD/LED state is visible. To keep it visible longer:

```powershell
python tools\serial_prediction_bridge.py --api-url http://127.0.0.1:8000 --email test.user@example.com --password SecurePass123! --port COM5 --hold-seconds 15
```

To force a specific demo scenario:

```powershell
python tools\serial_prediction_bridge.py --api-url http://127.0.0.1:8000 --email test.user@example.com --password SecurePass123! --port COM5 --transaction tools\transactions\high_risk.json --hold-seconds 15
python tools\serial_prediction_bridge.py --api-url http://127.0.0.1:8000 --email test.user@example.com --password SecurePass123! --port COM5 --transaction tools\transactions\low_risk.json --hold-seconds 15
```

Backend route used:

```text
POST /api/v1/auth/login
POST /api/v1/predict/transaction
```

Prediction mapping:

```text
risk_label = 1 -> send H to ESP32
risk_label = 0 -> send L to ESP32
```

## Integration Flow

```text
Transaction payload
        |
        v
Backend /api/v1/predict/transaction
        |
        v
risk_label / risk_probability
        |
        v
Python serial bridge
        |
        v
ESP32 LCD + buzzer + onboard LED
```
