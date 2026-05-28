"""M1 - User Access Management Start
Captures visible Edge evidence for admin user creation, sign-out, and first-login password reset.
M1 End"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

from PIL import ImageGrab


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests/scripts" / "common"))
from test_config import configured_path, configured_url, load_settings

SETTINGS = load_settings(__file__)
OUTPUT_DIR = configured_path(__file__, "evidenceFolders", "M1AdminUserFlow")
MODULE_ROOT = configured_path(__file__, "moduleFolders", "IdentityAccess")
WEB_ROOT = configured_path(__file__, "moduleFolders", "StatsWeb")
CAPTURE_DATE = "2026-05-23"
EDGE_EXECUTABLE = SETTINGS["localPaths"]["edgeExecutable"]
EDGE_USER_DATA = OUTPUT_DIR / f"edge-user-data-{int(time.time())}"
EDGE_DEBUG_PORT = int(SETTINGS["runtime"]["m1EdgeDebugPort"])
EDGE_SIZE = (1220, 860)
EDGE_POSITION = (25, 25)
SW_RESTORE = 9

ADMIN_EMAIL = "m1.regression.admin.20260523@example.com"
ADMIN_PASSWORD = "AdminTest123"
NEW_USER_EMAIL = "m1.regression.user.20260523@example.com"
NEW_USER_TEMP_PASSWORD = "UserTemp123"
NEW_USER_FINAL_PASSWORD = "UserReady123"

user32 = ctypes.windll.user32


class CdpClient:
    def __init__(self, websocket_url: str) -> None:
        parsed = urllib.parse.urlparse(websocket_url)
        self.path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.sock = socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or EDGE_DEBUG_PORT), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            f"Origin: http://{parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response:
            raise RuntimeError(f"CDP websocket handshake failed: {response!r}")
        self.next_id = 1

    def _send_frame(self, payload: str) -> None:
        data = payload.encode("utf-8")
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(header + masked)

    def _recv_frame(self) -> str:
        first = self.sock.recv(2)
        if len(first) < 2:
            raise RuntimeError("CDP websocket closed")
        length = first[1] & 0x7F
        if length == 126:
            length = int.from_bytes(self.sock.recv(2), "big")
        elif length == 127:
            length = int.from_bytes(self.sock.recv(8), "big")
        masked = bool(first[1] & 0x80)
        mask = self.sock.recv(4) if masked else b""
        payload = bytearray()
        while len(payload) < length:
            payload.extend(self.sock.recv(length - len(payload)))
        if masked:
            payload = bytearray(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return payload.decode("utf-8")

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self._send_frame(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self._recv_frame())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        remote = result.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return remote.get("value")


def window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def window_class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def visible_windows() -> list[tuple[int, str, str]]:
    windows: list[tuple[int, str, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_windows(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            title = window_text(hwnd)
            if title:
                windows.append((hwnd, title, window_class(hwnd)))
        return True

    user32.EnumWindows(enum_windows, 0)
    return windows


def wait_for_window(predicate: Callable[[int, str, str], bool], before: set[int]) -> int:
    for _ in range(50):
        for hwnd, title, class_name in visible_windows():
            if hwnd not in before and predicate(hwnd, title, class_name):
                return hwnd
        time.sleep(0.3)
    raise RuntimeError("Evidence window did not appear")


def wait_for_url(url: str) -> None:
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Local evidence target did not become ready: {url}")


def wait_for_cdp_target() -> str:
    for _ in range(40):
        try:
            targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/list", timeout=1).read())
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    return target["webSocketDebuggerUrl"]
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("Edge CDP target did not become ready")


def capture(hwnd: int, name: str) -> None:
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.MoveWindow(hwnd, EDGE_POSITION[0], EDGE_POSITION[1], EDGE_SIZE[0], EDGE_SIZE[1], True)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.5)
    output = OUTPUT_DIR / name
    ImageGrab.grab(bbox=window_rect(hwnd)).save(output)
    print(f"captured {output.name}")


def js_literal(value: str) -> str:
    return json.dumps(value)


def run_ui_flow(client: CdpClient, hwnd: int) -> None:
    client.call("Page.enable")
    client.call("Runtime.enable")
    client.call("Page.navigate", {"url": configured_url(__file__, "statsWebBaseUrl", "Login")})
    client.evaluate("""
        new Promise((resolve) => {
          if (document.readyState === 'complete') resolve(true);
          else window.addEventListener('load', () => resolve(true), { once: true });
        })
    """)

    client.evaluate(f"""
        new Promise((resolve, reject) => {{
          const email = document.querySelector('#email');
          const password = document.querySelector('#password');
          email.value = {js_literal(ADMIN_EMAIL)};
          password.value = {js_literal(ADMIN_PASSWORD)};
          document.querySelector('#login-form').requestSubmit();
          const started = Date.now();
          const timer = setInterval(() => {{
            if (location.pathname === '/') {{
              clearInterval(timer);
              resolve(true);
            }}
            if (Date.now() - started > 10000) {{
              clearInterval(timer);
              reject(new Error('Admin login did not reach main app'));
            }}
          }}, 250);
        }})
    """)

    client.call("Page.navigate", {"url": configured_url(__file__, "statsWebBaseUrl", "Users")})
    client.evaluate("""
        new Promise((resolve, reject) => {
          const started = Date.now();
          const timer = setInterval(() => {
            if (!document.querySelector('#users-workspace')?.hidden) {
              clearInterval(timer);
              resolve(true);
            }
            if (Date.now() - started > 10000) {
              clearInterval(timer);
              reject(new Error('User management workspace did not load'));
            }
          }, 250);
        })
    """)

    client.evaluate(f"""
        new Promise((resolve, reject) => {{
          document.querySelector('#full-name').value = 'M1 Regression User';
          document.querySelector('#user-email').value = {js_literal(NEW_USER_EMAIL)};
          document.querySelector('#temporary-password').value = {js_literal(NEW_USER_TEMP_PASSWORD)};
          document.querySelector('#role').value = 'user';
          document.querySelector('#is-active').checked = true;
          document.querySelector('#create-user-form').requestSubmit();
          const started = Date.now();
          const timer = setInterval(() => {{
            const message = document.querySelector('#create-message')?.textContent || '';
            const rows = Array.from(document.querySelectorAll('#user-rows tr')).map((row) => row.textContent);
            if (message.includes({js_literal(NEW_USER_EMAIL)}) && rows.some((text) => text.includes({js_literal(NEW_USER_EMAIL)}))) {{
              clearInterval(timer);
              resolve(true);
            }}
            if (Date.now() - started > 10000) {{
              clearInterval(timer);
              reject(new Error('Created user did not appear in the user list'));
            }}
          }}, 250);
        }})
    """)
    capture(hwnd, f"M1-AdminUserFlow-windows-browser-admin-created-user-{CAPTURE_DATE}.png")

    client.evaluate("""
        new Promise((resolve, reject) => {
          document.querySelector('#logout-button').click();
          const started = Date.now();
          const timer = setInterval(() => {
            if (location.pathname.toLowerCase() === '/login') {
              clearInterval(timer);
              resolve(true);
            }
            if (Date.now() - started > 10000) {
              clearInterval(timer);
              reject(new Error('Admin sign-out did not return to login'));
            }
          }, 250);
        })
    """)
    capture(hwnd, f"M1-AdminUserFlow-windows-browser-admin-signed-out-{CAPTURE_DATE}.png")

    client.evaluate(f"""
        new Promise((resolve, reject) => {{
          document.querySelector('#email').value = {js_literal(NEW_USER_EMAIL)};
          document.querySelector('#password').value = {js_literal(NEW_USER_TEMP_PASSWORD)};
          document.querySelector('#login-form').requestSubmit();
          const started = Date.now();
          const timer = setInterval(() => {{
            if (!document.querySelector('#password-setup-form')?.hidden) {{
              clearInterval(timer);
              resolve(true);
            }}
            if (Date.now() - started > 10000) {{
              clearInterval(timer);
              reject(new Error('New user did not reach password setup'));
            }}
          }}, 250);
        }})
    """)
    capture(hwnd, f"M1-AdminUserFlow-windows-browser-new-user-password-setup-{CAPTURE_DATE}.png")

    client.evaluate(f"""
        new Promise((resolve, reject) => {{
          document.querySelector('#new-password').value = {js_literal(NEW_USER_FINAL_PASSWORD)};
          document.querySelector('#confirm-password').value = {js_literal(NEW_USER_FINAL_PASSWORD)};
          document.querySelector('#password-setup-form').requestSubmit();
          const started = Date.now();
          const timer = setInterval(() => {{
            const email = document.querySelector('#current-user-email')?.textContent || '';
            if (location.pathname === '/' && email.includes({js_literal(NEW_USER_EMAIL)})) {{
              clearInterval(timer);
              resolve(true);
            }}
            if (Date.now() - started > 10000) {{
              clearInterval(timer);
              reject(new Error('New user did not reach main app after password reset'));
            }}
          }}, 250);
        }})
    """)
    capture(hwnd, f"M1-AdminUserFlow-windows-browser-new-user-main-app-{CAPTURE_DATE}.png")


def start_processes() -> list[subprocess.Popen[Any]]:
    processes: list[subprocess.Popen[Any]] = []
    env = os.environ.copy()
    env["API_PORT"] = SETTINGS["runtime"]["identityPort"]
    env["API_HOST"] = SETTINGS["runtime"]["identityHost"]
    env["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/stats"
    processes.append(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                SETTINGS["runtime"]["identityHost"],
                "--port",
                SETTINGS["runtime"]["identityPort"],
            ],
            cwd=MODULE_ROOT,
            env=env,
        )
    )
    processes.append(
        subprocess.Popen(
            ["dotnet", "run", "--urls", SETTINGS["runtime"]["statsWebBaseUrl"]],
            cwd=WEB_ROOT,
            env=env,
        )
    )
    return processes


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    setup = subprocess.run([sys.executable, str(SCRIPT_DIR / "M1-AdminUserFlow_setup_postgres.py")], cwd=MODULE_ROOT, check=True)
    if setup.returncode != 0:
        return setup.returncode

    processes = start_processes()
    node_process: subprocess.Popen[Any] | None = None
    try:
        wait_for_url(configured_url(__file__, "identityBaseUrl", "health"))
        wait_for_url(configured_url(__file__, "statsWebBaseUrl", "Login"))

        before = {hwnd for hwnd, _, _ in visible_windows()}
        node_env = os.environ.copy()
        bundled_node_modules = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules"
        if bundled_node_modules.exists():
            pnpm_node_modules = bundled_node_modules / ".pnpm" / "node_modules"
            node_paths = [str(bundled_node_modules)]
            if pnpm_node_modules.exists():
                node_paths.append(str(pnpm_node_modules))
            node_env["NODE_PATH"] = os.pathsep.join(node_paths)
        node_process = subprocess.Popen(
            ["node", str(SCRIPT_DIR / "M1-AdminUserFlow_playwright.js")],
            cwd=SCRIPT_DIR,
            env=node_env,
        )
        hwnd = wait_for_window(
            lambda window_hwnd, title, class_name: (
                window_hwnd not in before
                and class_name == "Chrome_WidgetWin_1"
                and "Welcome to Microsoft Edge" not in title
            ),
            before,
        )
        checkpoints = {
            "admin-created-user": f"M1-AdminUserFlow-windows-browser-admin-created-user-{CAPTURE_DATE}.png",
            "admin-signed-out": f"M1-AdminUserFlow-windows-browser-admin-signed-out-{CAPTURE_DATE}.png",
            "new-user-password-setup": f"M1-AdminUserFlow-windows-browser-new-user-password-setup-{CAPTURE_DATE}.png",
            "new-user-main-app": f"M1-AdminUserFlow-windows-browser-new-user-main-app-{CAPTURE_DATE}.png",
        }
        for marker, output_name in checkpoints.items():
            ready_path = OUTPUT_DIR / f"{marker}.ready"
            done_path = OUTPUT_DIR / f"{marker}.done"
            for _ in range(120):
                if ready_path.exists():
                    capture(hwnd, output_name)
                    done_path.write_text("captured", encoding="utf-8")
                    break
                if node_process.poll() is not None:
                    raise RuntimeError(f"Playwright flow exited before checkpoint: {marker}")
                time.sleep(0.25)
            else:
                raise RuntimeError(f"Timed out waiting for checkpoint: {marker}")
        node_exit = node_process.wait(timeout=60)
        if node_exit != 0:
            raise RuntimeError(f"Playwright evidence flow failed with exit code {node_exit}")
        print("M1 admin-created user browser evidence")
        print(f"Admin test user: {ADMIN_EMAIL}")
        print(f"Created user: {NEW_USER_EMAIL}")
        print("Temporary and reset passwords are test-only values.")
        print("Result: PASSED")
        return 0
    finally:
        if node_process is not None and node_process.poll() is None:
            node_process.terminate()
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
