import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial
from serial.tools import list_ports


HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "host",
    "keep-alive",
    "origin",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def list_serial_ports():
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return

    print("Available serial ports:")
    for port in ports:
        print(f"  {port.device} - {port.description}")


class Esp32SerialBridge:
    def __init__(self, port, baud, dry_run=False, ready_timeout=10.0, read_after_seconds=0.8):
        self.port = port
        self.baud = baud
        self.dry_run = dry_run
        self.ready_timeout = ready_timeout
        self.read_after_seconds = read_after_seconds
        self.serial = None
        self.lock = threading.Lock()

    def open(self):
        if self.dry_run:
            print("Dry run enabled; serial commands will be logged but not sent.")
            return

        self.serial = serial.Serial(self.port, baudrate=self.baud, timeout=0.25)
        print(f"Opened ESP32 serial port {self.port} at {self.baud} baud.")
        self._wait_for_ready()

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Closed ESP32 serial port.")

    def _wait_for_ready(self):
        deadline = time.monotonic() + self.ready_timeout
        print("Waiting for ESP32 startup/ready output...")

        while time.monotonic() < deadline:
            line = self._readline()
            if not line:
                continue

            print(f"ESP32: {line}")
            if "STATE: READY" in line or "Serial:" in line:
                return

        print("ESP32 ready output was not seen; continuing anyway.")

    def _readline(self):
        if not self.serial:
            return ""
        return self.serial.readline().decode("utf-8", errors="replace").strip()

    def _read_recent_lines(self):
        if not self.serial or self.read_after_seconds <= 0:
            return

        deadline = time.monotonic() + self.read_after_seconds
        while time.monotonic() < deadline:
            line = self._readline()
            if line:
                print(f"ESP32: {line}")

    def send_probability(self, probability, threshold):
        command = "H" if probability >= threshold else "L"
        risk_text = "HIGH" if command == "H" else "LOW"

        with self.lock:
            if self.dry_run:
                print(f"DRY RUN: probability={probability:.4f} threshold={threshold:.4f} -> {risk_text} -> {command}")
                return command

            if not self.serial or not self.serial.is_open:
                raise RuntimeError("ESP32 serial port is not open.")

            self.serial.write(command.encode("ascii"))
            self.serial.flush()
            print(f"Sent ESP32 command {command} for {risk_text} risk ({probability:.4f}).")
            self._read_recent_lines()
            return command


class ImmediateDispatcher:
    def __init__(self, bridge, threshold):
        self.bridge = bridge
        self.threshold = threshold

    def start(self):
        return

    def stop(self):
        return

    def dispatch_probability(self, probability):
        thread = threading.Thread(
            target=self.bridge.send_probability,
            args=(probability, self.threshold),
            daemon=True,
        )
        thread.start()


class PredictionProxyHandler(BaseHTTPRequestHandler):
    server_version = "SmartWalletPredictionProxy/1.0"

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._proxy_request()

    def do_POST(self):
        self._proxy_request()

    def do_PUT(self):
        self._proxy_request()

    def do_PATCH(self):
        self._proxy_request()

    def do_DELETE(self):
        self._proxy_request()

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def _send_cors_headers(self):
        requested_headers = self.headers.get(
            "Access-Control-Request-Headers",
            "Authorization, Content-Type, Accept, Origin, X-Requested-With",
        )
        origin = self.headers.get("Origin") or self.server.cors_origin
        allow_origin = origin if self.server.cors_origin == "*" else self.server.cors_origin

        self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", requested_headers)
        self.send_header("Access-Control-Max-Age", "86400")

    def _proxy_request(self):
        body = self._read_body()
        target_url = self.server.backend_url.rstrip("/") + self.path
        headers = self._forward_headers()

        request = urllib.request.Request(
            target_url,
            data=body if self.command in {"POST", "PUT", "PATCH"} else None,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.server.backend_timeout) as response:
                response_body = response.read()
                status = response.status
                response_headers = response.headers
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status = exc.code
            response_headers = exc.headers
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            message = {
                "detail": f"Prediction proxy could not reach backend at {self.server.backend_url}: {reason}"
            }
            response_body = json.dumps(message).encode("utf-8")
            status = 502
            response_headers = {"Content-Type": "application/json"}

        self._send_response(status, response_headers, response_body)
        self._handle_prediction_response(status, response_body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _forward_headers(self):
        headers = {}
        for name, value in self.headers.items():
            if name.lower() in HOP_BY_HOP_HEADERS:
                continue
            headers[name] = value
        return headers

    def _send_response(self, status, response_headers, response_body):
        self.send_response(status)
        self._send_cors_headers()

        content_type = response_headers.get("Content-Type") if hasattr(response_headers, "get") else None
        if content_type:
            self.send_header("Content-Type", content_type)

        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _handle_prediction_response(self, status, response_body):
        if self.command != "POST":
            return
        if self.path.split("?", 1)[0] != "/api/v1/predict/transaction":
            return
        if not (200 <= status < 300):
            print(f"Prediction request returned HTTP {status}; no ESP32 command sent.")
            return

        try:
            payload = json.loads(response_body.decode("utf-8"))
            probability = float(payload["risk_probability"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"Could not parse prediction response for ESP32 command: {exc}")
            return

        self.server.dispatcher.dispatch_probability(probability)


class PredictionProxyServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        handler_class,
        backend_url,
        dispatcher,
        cors_origin,
        backend_timeout,
    ):
        super().__init__(server_address, handler_class)
        self.backend_url = backend_url
        self.dispatcher = dispatcher
        self.cors_origin = cors_origin
        self.backend_timeout = backend_timeout


def add_common_arguments(parser):
    parser.add_argument("--list-ports", action="store_true", help="List available serial ports and exit.")
    parser.add_argument("--port", help="ESP32 serial port, for example COM5.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8000)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8001")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--cors-origin", default="*")
    parser.add_argument("--backend-timeout", type=float, default=30.0)
    parser.add_argument("--ready-timeout", type=float, default=10.0)
    parser.add_argument("--read-after-seconds", type=float, default=0.8)
    parser.add_argument("--dry-run", action="store_true", help="Run without opening a serial port.")


def create_bridge(args):
    return Esp32SerialBridge(
        port=args.port,
        baud=args.baud,
        dry_run=args.dry_run,
        ready_timeout=args.ready_timeout,
        read_after_seconds=args.read_after_seconds,
    )


def validate_args(args):
    if args.list_ports:
        list_serial_ports()
        return False

    if not args.dry_run and not args.port:
        print("Missing --port. Use --list-ports to find the ESP32 COM port.", file=sys.stderr)
        raise SystemExit(2)

    return True


def run_server(args, bridge, dispatcher, dispatch_description):
    try:
        bridge.open()
        dispatcher.start()
        server = PredictionProxyServer(
            (args.listen_host, args.listen_port),
            PredictionProxyHandler,
            backend_url=args.backend_url,
            dispatcher=dispatcher,
            cors_origin=args.cors_origin,
            backend_timeout=args.backend_timeout,
        )

        print(
            f"Prediction proxy listening on http://{args.listen_host}:{args.listen_port} "
            f"and forwarding to {args.backend_url}."
        )
        print(f"{dispatch_description}; threshold: {args.threshold:.4f}.")
        print("Run the real backend on the backend URL above, then use the frontend normally.")
        print("Press Ctrl+C to stop.")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping prediction proxy.")
    finally:
        dispatcher.stop()
        bridge.close()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=(
            "No-polling proxy: forward frontend API calls to the backend and send H/L to ESP32 "
            "immediately when /api/v1/predict/transaction returns risk_probability."
        )
    )
    add_common_arguments(parser)
    args = parser.parse_args()

    if not validate_args(args):
        return 0

    bridge = create_bridge(args)
    dispatcher = ImmediateDispatcher(bridge=bridge, threshold=args.threshold)
    return run_server(args, bridge, dispatcher, "Dispatch mode: no polling/immediate")


if __name__ == "__main__":
    raise SystemExit(main())
