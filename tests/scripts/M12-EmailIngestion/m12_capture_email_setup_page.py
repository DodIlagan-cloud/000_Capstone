from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path

from PIL import ImageGrab


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "tests" / "results" / "M12-EmailIngestion"
BASE_URL = "http://127.0.0.1:8080"
PORT = 9462
PROFILE = RESULTS / "edge-profile-email-setup-only"
EDGE = os.environ.get("STATS_EDGE_EXECUTABLE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
ADMIN_EMAIL = os.environ.get("STATS_EVIDENCE_ADMIN_EMAIL", "m12.evidence.admin@example.test")
ADMIN_PASSWORD = os.environ.get("STATS_EVIDENCE_ADMIN_PASSWORD", "")
TODAY = "2026-07-02"


class CdpClient:
    def __init__(self, ws_url: str):
        self.next_id = 1
        self.sock = self._connect(ws_url)

    def _connect(self, ws_url: str) -> socket.socket:
        without_scheme = ws_url[len("ws://") :]
        host_port, path = without_scheme.split("/", 1)
        host, port_text = host_port.split(":", 1)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock = socket.create_connection((host, int(port_text)), timeout=10)
        request = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {host_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = sock.recv(4096)
        if b" 101 " not in response:
            raise RuntimeError(f"WebSocket upgrade failed: {response!r}")
        return sock

    def _send_frame(self, payload: bytes) -> None:
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.extend([0x80 | 126])
            header.extend(struct.pack("!H", length))
        else:
            header.extend([0x80 | 127])
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_frame(self) -> dict:
        first = self.sock.recv(2)
        if len(first) < 2:
            return {}
        opcode = first[0] & 0x0F
        length = first[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.sock.recv(8))[0]
        payload = b""
        while len(payload) < length:
            payload += self.sock.recv(length - len(payload))
        if opcode not in (1, 0):
            return {}
        return json.loads(payload.decode("utf-8"))

    def call(self, method: str, params: dict | None = None, timeout: float = 20) -> dict:
        message_id = self.next_id
        self.next_id += 1
        self._send_frame(json.dumps({"id": message_id, "method": method, "params": params or {}}).encode("utf-8"))
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self._recv_frame()
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"CDP {method} failed: {message['error']}")
                return message.get("result", {})
        raise TimeoutError(method)

    def eval(self, expression: str, timeout: float = 20):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
            timeout=timeout,
        )
        return result.get("result", {}).get("value")


def wait_for(cdp: CdpClient, expression: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.eval(expression, timeout=4):
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise TimeoutError(expression)


def js(value: str) -> str:
    return json.dumps(value)


def open_edge() -> str:
    PROFILE.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1):
            pass
    except Exception:
        subprocess.Popen(
            [
                EDGE,
                f"--remote-debugging-port={PORT}",
                f"--user-data-dir={PROFILE}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=msEdgeWelcomePage",
                "--new-window",
                "about:blank",
            ],
            cwd=ROOT,
        )
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")
            with urllib.request.urlopen(request, timeout=2) as response:
                target = json.loads(response.read().decode("utf-8"))
            if target.get("webSocketDebuggerUrl"):
                return target["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("Edge remote debugger did not become available")


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def find_window(title_fragment: str) -> int:
    user32 = ctypes.windll.user32
    found: list[int] = []

    def enum_windows(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if title_fragment.lower() in buffer.value.lower():
            found.append(hwnd)
            return False
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(callback, None)
    if not found:
        raise RuntimeError(f"Could not find window containing title: {title_fragment}")
    return found[0]


def capture_email_setup(cdp: CdpClient) -> Path:
    cdp.call("Page.bringToFront")
    try:
        window = cdp.call("Browser.getWindowForTarget")
        cdp.call(
            "Browser.setWindowBounds",
            {"windowId": window["windowId"], "bounds": {"left": 40, "top": 24, "width": 1280, "height": 900, "windowState": "normal"}},
        )
    except Exception:
        pass
    hwnd = find_window("Stats Email Ingestion Setup")
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1)
    RESULTS.mkdir(parents=True, exist_ok=True)
    output = RESULTS / f"m12-email-setup-page-{TODAY}.png"
    ImageGrab.grab(bbox=window_rect(hwnd)).save(output)
    return output


def main() -> None:
    ws_url = open_edge()
    cdp = CdpClient(ws_url)
    cdp.call("Page.navigate", {"url": f"{BASE_URL}/EmailSetup"})
    wait_for(cdp, "document.readyState === 'complete'", timeout=30)
    if cdp.eval("location.pathname === '/Login'"):
        if not ADMIN_PASSWORD:
            raise SystemExit("STATS_EVIDENCE_ADMIN_PASSWORD is required when the browser is not already signed in.")
        login_ok = cdp.eval(
            f"""
            (async () => {{
              const login = await fetch('/api/v1/auth/login', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ email: {js(ADMIN_EMAIL)}, password: {js(ADMIN_PASSWORD)} }})
              }});
              if (!login.ok) {{
                return false;
              }}
              const me = await fetch('/api/v1/auth/me', {{ headers: {{ 'X-Stats-CSRF': '1' }} }});
              return me.ok;
            }})()
            """
        )
        if not login_ok:
            raise SystemExit("Browser-origin login failed for the evidence admin account.")
        cdp.call("Page.navigate", {"url": f"{BASE_URL}/EmailSetup"})
    wait_for(
        cdp,
        "document.readyState === 'complete' && location.pathname === '/EmailSetup' && document.body.innerText.includes('Email ingestion setup')",
        timeout=45,
    )
    path = capture_email_setup(cdp)
    print(path)
    print("Result: PASSED")


if __name__ == "__main__":
    main()
