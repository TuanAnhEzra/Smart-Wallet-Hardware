# Smart Wallet Hardware Alert Module

This ESP32-S3 module displays the prediction result from the Smart Wallet backend.

- `H`: high overspending risk, show LCD warning, flash red onboard LED, beep buzzer
- `L`: low risk, show safe message, green onboard LED
- `R`: ready state

The local buttons still test the hardware without the frontend/backend.

## Current Wiring

| Part | ESP32-S3 Pin |
| --- | --- |
| Buzzer | GPIO4 |
| LCD SDA | GPIO8 |
| LCD SCL | GPIO9 |
| Red LED | GPIO42 |
| Yellow LED | GPIO41 |
| Green LED | GPIO40 |
| Red button | GPIO10 |
| Yellow button | GPIO11 |
| Green button | GPIO12 |

Buttons use `INPUT_PULLUP`, so wire each button between its GPIO pin and GND.
Use a resistor in series with each external LED.

## Manual Serial Test

Upload the firmware and open the PlatformIO serial monitor at `115200` baud.
Send one of these commands:

```text
H
L
R
W
A
B
0
```

`H` shows high risk with the red LED and buzzer. `L` shows low risk with the
green LED. `W` shows warning with the yellow LED. `R` returns to ready. `A`
runs the full component test, `B` tests the buzzer, and `0` turns outputs off.

## Live Frontend Prediction Test

For the real localhost demo, do not use PlatformIO serial monitor. The Python
proxy must own the ESP32 serial port.

The frontend already sends API calls to `http://localhost:8000`. The hardware
proxy listens on that port, forwards every request to the real backend on
`http://127.0.0.1:8001`, and only intercepts prediction responses:

```text
Frontend localhost:5173
        |
        v
Hardware proxy localhost:8000
        |
        v
Backend localhost:8001
        |
        v
risk_probability >= 0.5 -> send H to ESP32
risk_probability < 0.5  -> send L to ESP32
```

Start the backend on port `8001`:

```powershell
cd ..\backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

In another terminal, start one hardware proxy from `hardware/`.
Both proxy scripts are standalone; choose either one.

Option 1: no polling. This sends `H` or `L` immediately after the proxy receives
the backend prediction response:

```powershell
python tools\live_prediction_proxy_no_polling.py --list-ports
python tools\live_prediction_proxy_no_polling.py --backend-url http://127.0.0.1:8001 --port COM5
```

Replace `COM5` with the ESP32 port shown by `--list-ports`.

Option 2: with polling. This queues prediction results and lets a polling worker
check for new results every interval:

```powershell
python tools\live_prediction_proxy_polling.py --backend-url http://127.0.0.1:8001 --port COM5 --poll-interval 0.25
```

In another terminal, start the frontend:

```powershell
cd ..\frontend
npm.cmd run dev
```

Open:

```text
http://localhost:5173
```

Log in, go to the Prediction/Alerts page, enter transaction values, and press
the prediction button. The backend response controls the ESP32 through the
proxy.

## Standalone Payload Bridge Test

This older bridge script calls the backend prediction endpoint with a JSON file
and forwards the result to the ESP32 over serial. It is useful for isolated
hardware/backend testing, but it does not use the frontend prediction page.

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
