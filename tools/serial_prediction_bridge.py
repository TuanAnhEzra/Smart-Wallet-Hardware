import argparse
import json
import sys
import time
import urllib.error
import urllib.request

import serial
from serial.tools import list_ports


DEFAULT_TRANSACTION = {
    "amount": 400.0,
    "category": "shopping",
    "hour": 19,
    "day_of_week": 5,
    "is_weekend": 1,
    "balance_before": 1500.0,
    "monthly_income": 5000.0,
    "monthly_budget": 2000.0,
    "daily_spent_so_far": 400.0,
    "weekly_spent_so_far": 900.0,
    "monthly_spent_so_far": 1800.0,
    "avg_amount_user": 35.0,
    "avg_amount_category_user": 80.0,
    "remaining_budget_month": 200.0,
    "remaining_budget_ratio": 0.1,
    "amount_vs_user_avg": 11.43,
    "amount_vs_category_avg": 5.0,
}


def post_json(url, payload, token=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc


def login(api_url, email, password):
    response = post_json(
        f"{api_url}/api/v1/auth/login",
        {"email": email, "password": password},
    )
    token = response.get("access_token")
    if not token:
        raise RuntimeError("Login response did not include access_token")
    return token


def predict(api_url, token, transaction):
    return post_json(f"{api_url}/api/v1/predict/transaction", transaction, token=token)


def load_transaction(path):
    if not path:
        return DEFAULT_TRANSACTION

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def list_serial_ports():
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return

    print("Available serial ports:")
    for port in ports:
        print(f"  {port.device} - {port.description}")


def read_serial_lines(esp32, duration_seconds):
    deadline = time.monotonic() + duration_seconds
    while time.monotonic() < deadline:
        line = esp32.readline().decode("utf-8", errors="replace").strip()
        if line:
            print(f"ESP32: {line}")


def wait_for_esp32_ready(esp32, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        line = esp32.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue

        print(f"ESP32: {line}")
        if "Commands:" in line or "STATE: READY" in line:
            return True

    return False


def send_risk_to_esp32(port, baud, risk_label, ready_timeout, hold_seconds):
    command = b"H" if risk_label == 1 else b"L"
    with serial.Serial(port, baudrate=baud, timeout=0.5) as esp32:
        print("Waiting for ESP32 serial startup...")
        if not wait_for_esp32_ready(esp32, ready_timeout):
            print("ESP32 ready message not seen; sending command anyway.")

        esp32.write(command)
        esp32.flush()
        read_serial_lines(esp32, hold_seconds)

    return command.decode("ascii")


def main():
    parser = argparse.ArgumentParser(
        description="Call the Smart Wallet backend prediction API and forward the result to ESP32 over serial."
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--port", help="ESP32 serial port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--transaction", help="Path to a JSON transaction payload")
    parser.add_argument("--ready-timeout", type=float, default=8.0)
    parser.add_argument("--hold-seconds", type=float, default=6.0)
    parser.add_argument("--list-ports", action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        list_serial_ports()
        return 0

    missing = [
        name
        for name, value in {
            "--email": args.email,
            "--password": args.password,
            "--port": args.port,
        }.items()
        if not value
    ]
    if missing:
        print(f"Missing required arguments: {', '.join(missing)}", file=sys.stderr)
        print("Tip: use --list-ports to find your ESP32 COM port.", file=sys.stderr)
        return 2

    transaction = load_transaction(args.transaction)
    token = login(args.api_url.rstrip("/"), args.email, args.password)
    result = predict(args.api_url.rstrip("/"), token, transaction)

    risk_label = int(result["risk_label"])
    probability = float(result["risk_probability"])
    risk_text = "HIGH" if risk_label == 1 else "LOW"
    print(f"Backend risk: {risk_text} ({probability:.4f})")

    command = send_risk_to_esp32(
        args.port,
        args.baud,
        risk_label,
        ready_timeout=args.ready_timeout,
        hold_seconds=args.hold_seconds,
    )

    print(f"Sent serial command to ESP32: {command}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Bridge error: {exc}", file=sys.stderr)
        print(
            "Make sure the backend is running and reachable at --api-url before running the bridge.",
            file=sys.stderr,
        )
        raise SystemExit(1)
