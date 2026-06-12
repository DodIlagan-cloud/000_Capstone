"""Capture M3/M4 duplicate upload user-flow evidence through the local Stats app.

This is a local-only evidence runner. It drives the visible Stats Web UI at
http://127.0.0.1:8080 and records screenshots plus raw output under tests/results.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import ImageGrab


ROOT = Path(__file__).resolve().parents[3]
DATE = "2026-06-12"
STAMP = time.strftime("%Y%m%d-%H%M%S")
RUN_ID = secrets.token_hex(4)
BASE_URL = "http://127.0.0.1:8080"
EVIDENCE = ROOT / "tests" / "results" / "M3-M4-DuplicateUploadUserFlow" / f"M3-M4-duplicate-upload-user-flow-{DATE}-{STAMP}"
PROFILE = EVIDENCE / f"edge-profile-{RUN_ID}"
RAW_OUTPUT = EVIDENCE / f"M3-M4-duplicate-upload-user-flow-raw-output-{DATE}.txt"
FIXTURE = ROOT / "tests" / "input" / "202312_HSBC_4028-9391-1618-2659.pdf"
EDGE = os.environ.get("STATS_EDGE_EXECUTABLE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
PORT = 9400 + (int(time.time()) % 400)
ADMIN_EMAIL = f"m3m4.duplicate.{STAMP}.{RUN_ID}@example.test"
ADMIN_PASSWORD = f"Stats{secrets.token_hex(8)}7"


def append_raw(message: str = "") -> None:
    print(message)
    with RAW_OUTPUT.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result


class CdpClient:
    def __init__(self, ws_url: str):
        self.next_id = 1
        self.sock = self._connect(ws_url)

    def _connect(self, ws_url: str) -> socket.socket:
        without_scheme = ws_url.removeprefix("ws://")
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
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, n: int) -> bytes:
        chunks: list[bytes] = []
        remaining = n
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("WebSocket closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_frame(self) -> dict:
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        payload = self._recv_exact(length)
        if opcode == 8:
            raise RuntimeError("WebSocket close frame received")
        if opcode not in (0, 1):
            return {}
        return json.loads(payload.decode("utf-8"))

    def call(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
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

    def eval(self, expression: str, timeout: float = 30):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
            timeout=timeout,
        )
        return result.get("result", {}).get("value")


def js(value: str) -> str:
    return json.dumps(value)


def wait_for(cdp: CdpClient, expression: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.eval(expression, timeout=5):
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise TimeoutError(expression)


def wait_for_health() -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError("Stats Web health endpoint did not become ready")


def wait_for_debugger() -> str:
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2) as response:
                targets = json.loads(response.read().decode("utf-8"))
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    return target["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("Edge remote debugger did not become available")


def navigate(cdp: CdpClient, path: str) -> None:
    cdp.call("Page.navigate", {"url": f"{BASE_URL}{path}"})
    wait_for(cdp, "document.readyState === 'complete'", timeout=30)


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def find_window_by_bounds(title_fragment: str, left: int, top: int, width: int, height: int) -> int:
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
        if title_fragment.lower() not in buffer.value.lower():
            return True
        rect = window_rect(hwnd)
        rect_width = rect[2] - rect[0]
        rect_height = rect[3] - rect[1]
        if abs(rect[0] - left) <= 16 and abs(rect[1] - top) <= 16 and abs(rect_width - width) <= 40 and abs(rect_height - height) <= 80:
            found.append(hwnd)
            return False
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(callback, None)
    if not found:
        raise RuntimeError("Could not find Edge window by expected bounds")
    return found[0]


def crop_hwnd_screenshot(path: Path, hwnd: int) -> Path:
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1)
    ImageGrab.grab(bbox=window_rect(hwnd)).save(path)
    append_raw(f"Screenshot: {path}")
    return path


def browser_screenshot(cdp: CdpClient, name: str) -> Path:
    cdp.call("Page.bringToFront")
    left, top, width, height = 28, 20, 1280, 900
    try:
        window = cdp.call("Browser.getWindowForTarget")
        cdp.call(
            "Browser.setWindowBounds",
            {"windowId": window["windowId"], "bounds": {"left": left, "top": top, "width": width, "height": height, "windowState": "normal"}},
        )
    except Exception:
        pass
    try:
        hwnd = find_window_by_bounds("Stats", left, top, width, height)
    except Exception:
        hwnd = find_any_window("Stats")
    return crop_hwnd_screenshot(EVIDENCE / f"{name}.png", hwnd)


def seed_admin() -> None:
    seed_script = f"""
from app.db import SessionLocal
from app.models.user import User
from app.utils.security import hash_password

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == {ADMIN_EMAIL!r}).one_or_none()
    if user is None:
        user = User(email={ADMIN_EMAIL!r}, full_name="M3 M4 Duplicate Evidence User", role="admin")
        db.add(user)
    user.hashed_password = hash_password({ADMIN_PASSWORD!r})
    user.must_change_password = False
    user.is_active = True
    user.role = "admin"
    db.commit()
    print("Evidence admin ready")
finally:
    db.close()
"""
    result = run(
        [
            "docker",
            "exec",
            "--workdir",
            "/app/modules/identity-access-module",
            "stats-runtime",
            "/opt/stats/runtime/bin/python",
            "-c",
            seed_script,
        ]
    )
    append_raw(result.stdout.strip())


def cleanup_admin() -> None:
    cleanup_script = f"""
from app.db import SessionLocal
from app.models.user import User

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == {ADMIN_EMAIL!r}).one_or_none()
    if user is not None:
        db.delete(user)
        db.commit()
        print("Evidence admin removed")
    else:
        print("Evidence admin already absent")
finally:
    db.close()
"""
    result = run(
        [
            "docker",
            "exec",
            "--workdir",
            "/app/modules/identity-access-module",
            "stats-runtime",
            "/opt/stats/runtime/bin/python",
            "-c",
            cleanup_script,
        ],
        check=False,
    )
    append_raw((result.stdout or result.stderr).strip())


def set_file(cdp: CdpClient, path: Path) -> None:
    document = cdp.call("DOM.getDocument", {"depth": 1})
    root_node = document["root"]["nodeId"]
    node = cdp.call("DOM.querySelector", {"nodeId": root_node, "selector": "#document-file"})["nodeId"]
    cdp.call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(path)]})
    wait_for(cdp, "document.querySelector('#document-file')?.files?.length === 1", timeout=10)


def install_fetch_probe(cdp: CdpClient) -> None:
    cdp.eval(
        """
        (() => {
          window.__m3m4FetchCalls = [];
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const target = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
            window.__m3m4FetchCalls.push(String(target));
            return originalFetch(...args);
          };
          return true;
        })()
        """
    )


def upload_state(cdp: CdpClient) -> dict:
    return cdp.eval(
        """
        (() => ({
          url: location.href,
          upload_state: document.querySelector('#upload-state')?.innerText || '',
          validation: document.querySelector('#validation-result')?.innerText || '',
          ingestion: document.querySelector('#ingestion-result')?.innerText || '',
          processing: document.querySelector('#parse-result')?.innerText || '',
          fetch_calls: window.__m3m4FetchCalls || [],
          body_text: document.body.innerText.slice(0, 4000)
        }))()
        """,
        timeout=10,
    )


def write_evidence_docs(rows: list[tuple[str, Path, str, str]], first_state: dict, duplicate_state: dict, pytest_summary: str, result: str) -> None:
    index_lines = [
        "# M3/M4 Duplicate Upload User-Flow Screenshot Evidence",
        "",
        f"- Date: {DATE}",
        f"- Runtime: `{BASE_URL}` through local `stats-runtime`",
        f"- Fixture: `{FIXTURE.name}`",
        f"- Result: `{result}`",
        "",
        "| Evidence | File | Reviewer Check | Result / Comment |",
        "| --- | --- | --- | --- |",
    ]
    for label, path, check, comment in rows:
        index_lines.append(f"| {label} | `{path.name}` | {check} | {comment} |")
    (EVIDENCE / f"M3-M4-duplicate-upload-screenshot-evidence-{DATE}.md").write_text("\n".join(index_lines), encoding="utf-8")

    walkthrough_lines = [
        "# M3/M4 Duplicate Upload User-Flow Reviewer Walkthrough",
        "",
        "## Objective",
        "Prove through the actual Stats app UI that duplicate M3/M4 ingestion is terminal and does not continue into M5/M7/M8 processing, while the first queued upload starts normal processing.",
        "",
        "## Runtime",
        f"- Base URL: `{BASE_URL}`",
        "- Container: `stats-runtime`",
        f"- Evidence folder: `{EVIDENCE}`",
        f"- Fixture: `{FIXTURE}`",
        "",
        "## Step-By-Step Review",
        "",
        "| Step | Screenshot | Reviewer Checks | Result / Comment |",
        "| --- | --- | --- | --- |",
    ]
    for label, path, check, comment in rows:
        walkthrough_lines.append(f"| {label} | `{path.name}` | {check} | {comment} |")
    walkthrough_lines.extend(["", "## Embedded Screenshots", ""])
    for label, path, check, comment in rows:
        visual_result = "Pass - expected result is visible in this screenshot." if comment.lower().startswith("pass") or comment.lower().startswith("passed") else "Needs review - expected result may not be visible in this screenshot."
        walkthrough_lines.extend(
            [
                f"### {label}",
                f"![{label}]({path.name})",
                "",
                f"- Reviewer check: {check}",
                f"- Visual result check: {visual_result}",
                f"- Result / comment: {comment}",
                "",
            ]
        )
    duplicate_upload_job_calls = [call for call in duplicate_state.get("fetch_calls", []) if "/api/v1/upload-processing-jobs" in call]
    duplicate_transaction_results_visible = "Transaction check results" in duplicate_state.get("body_text", "")
    walkthrough_lines.extend(
        [
            "",
            "## State Assertions",
            f"- First upload ingestion text contains queued: `{('Status queued' in first_state.get('ingestion', '') or 'queued' in first_state.get('ingestion', '').lower())}`",
            f"- Duplicate upload state contains duplicate message: `{('already uploaded' in duplicate_state.get('body_text', '').lower())}`",
            f"- Duplicate upload processing-job calls captured by browser probe: `{len(duplicate_upload_job_calls)}`",
            f"- Duplicate upload transaction result panel visible: `{duplicate_transaction_results_visible}`",
            "",
            "## Container Pytest Support",
            "```text",
            pytest_summary.strip(),
            "```",
            "",
            f"Final result: `{result}`",
        ]
    )
    (EVIDENCE / f"M3-M4-duplicate-upload-reviewer-walkthrough-{DATE}.md").write_text("\n".join(walkthrough_lines), encoding="utf-8")

    summary = {
        "result": result,
        "base_url": BASE_URL,
        "fixture": str(FIXTURE),
        "first_state": first_state,
        "duplicate_state": duplicate_state,
        "duplicate_upload_processing_job_calls": duplicate_upload_job_calls,
        "pytest_summary": pytest_summary,
    }
    (EVIDENCE / "M3-M4-duplicate-upload-state-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def run_targeted_pytest() -> str:
    commands = [
        [
            "docker",
            "exec",
            "stats-runtime",
            "sh",
            "-lc",
            "cd /app && /opt/stats/runtime/bin/python -m pytest "
            "tests/integration/test_stats_web_orchestration_config.py::test_upload_duplicate_ingestion_stops_before_async_m5_m7_processing "
            "tests/integration/test_stats_web_orchestration_config.py::test_queued_ingestion_still_reaches_m7_extraction_after_m5_parse "
            "tests/unit/transaction_extraction_module/test_extraction_service.py::test_missing_text_fails_with_explicit_finding -q",
        ],
        [
            "docker",
            "exec",
            "stats-runtime",
            "sh",
            "-lc",
            "cd /app && STATS_TESTDATA_DIR=/app/tests/input /opt/stats/runtime/bin/python -m pytest "
            "tests/unit/file_validation_module/test_ingestion_api.py::test_create_ingestion_returns_duplicate_for_idempotent_real_pdf_submission -q",
        ],
    ]
    chunks: list[str] = []
    for command in commands:
        result = run(command, check=False)
        chunks.append("$ " + " ".join(command))
        chunks.append(result.stdout.strip())
        if result.stderr.strip():
            chunks.append(result.stderr.strip())
        if result.returncode != 0:
            raise RuntimeError("\n".join(chunks))
    return "\n".join(chunks)


def capture_terminal_summary() -> Path:
    terminal_script = EVIDENCE / "show_terminal_summary.ps1"
    terminal_script.write_text(
        f"$host.UI.RawUI.WindowTitle = 'M3M4 duplicate upload terminal evidence'; Get-Content -LiteralPath '{RAW_OUTPUT}'",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [
            "powershell.exe",
            "-NoExit",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(terminal_script),
        ],
        cwd=ROOT,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    time.sleep(3)
    hwnd = find_any_window("M3M4 duplicate upload terminal evidence")
    path = EVIDENCE / f"07-terminal-result-{DATE}.png"
    crop_hwnd_screenshot(path, hwnd)
    try:
        process.terminate()
    except Exception:
        pass
    return path


def find_any_window(title_fragment: str) -> int:
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


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT.write_text("", encoding="utf-8")
    append_raw("M3/M4 duplicate upload user-flow evidence")
    append_raw(f"Date: {DATE}")
    append_raw(f"Runtime: {BASE_URL}")
    append_raw(f"Fixture: {FIXTURE}")
    append_raw("Secrets: runtime password generated and intentionally not logged")
    wait_for_health()
    append_raw("Stats Web health: PASSED")
    seed_admin()

    rows: list[tuple[str, Path, str, str]] = []
    edge_process: subprocess.Popen | None = None
    cdp: CdpClient | None = None
    result = "FAILED"
    first_state: dict = {}
    duplicate_state: dict = {}
    pytest_summary = ""
    try:
        edge_process = subprocess.Popen(
            [
                EDGE,
                f"--remote-debugging-port={PORT}",
                f"--user-data-dir={PROFILE}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                "--disable-features=msEdgeWelcomePage,msUndersideButton",
                "--new-window",
                f"{BASE_URL}/Login",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cdp = CdpClient(wait_for_debugger())
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")

        navigate(cdp, "/Login")
        wait_for(cdp, "document.body.innerText.includes('Sign in')")
        shot = browser_screenshot(cdp, f"01-login-{DATE}")
        rows.append(("Login page", shot, "Address bar shows /Login and the Stats sign-in form is visible.", "Pass - login page loaded from the local runtime."))

        cdp.eval(
            f"""
            (() => {{
              document.querySelector('#email').value = {js(ADMIN_EMAIL)};
              document.querySelector('#password').value = {js(ADMIN_PASSWORD)};
              document.querySelector('#login-form').requestSubmit();
              return true;
            }})()
            """
        )
        wait_for(cdp, "location.pathname === '/' && document.body.innerText.includes('Access granted')", timeout=40)
        shot = browser_screenshot(cdp, f"02-authenticated-home-{DATE}")
        rows.append(("Authenticated home", shot, "User is signed in and the normal Stats shell is visible.", "Pass - temporary evidence user authenticated."))

        navigate(cdp, "/Upload")
        wait_for(cdp, "!!document.querySelector('#document-drop-zone') && document.body.innerText.includes('Drop document here')", timeout=30)
        shot = browser_screenshot(cdp, f"03-upload-drop-zone-{DATE}")
        rows.append(("Upload drop zone", shot, "Upload page shows the drag/drop zone and browse input.", "Pass - upload UI is reachable and shows drag/drop behavior."))

        set_file(cdp, FIXTURE)
        try:
            wait_for(
                cdp,
                """
                (() => {
                  const text = document.body.innerText.toLowerCase();
                  const ingestion = document.querySelector('#ingestion-result')?.innerText.toLowerCase() || '';
                  const upload = document.querySelector('#upload-state')?.innerText.toLowerCase() || '';
                  return ingestion.length > 0
                    || upload.includes('failed')
                    || upload.includes('stopped')
                    || text.includes('already uploaded')
                    || text.includes('rejected');
                })()
                """,
                timeout=90,
            )
        except TimeoutError:
            append_raw("First upload state wait: TIMED OUT")
        first_state = upload_state(cdp)
        (EVIDENCE / "first-upload-state.json").write_text(json.dumps(first_state, indent=2), encoding="utf-8")
        first_queued = "queued" in first_state.get("ingestion", "").lower()
        if first_queued:
            append_raw("First upload queued: PASSED")
            shot = browser_screenshot(cdp, f"04-first-upload-queued-{DATE}")
            rows.append(("First upload queued", shot, "The real fixture has an ingestion result with Status queued and starts normal processing.", "Pass - first upload reached the normal queued handoff."))

            navigate(cdp, "/Upload")
            wait_for(cdp, "!!document.querySelector('#document-file')", timeout=30)
            install_fetch_probe(cdp)
            set_file(cdp, FIXTURE)
            try:
                wait_for(cdp, "document.body.innerText.toLowerCase().includes('already uploaded')", timeout=60)
            except TimeoutError:
                append_raw("Duplicate upload terminal state wait: TIMED OUT")
            time.sleep(2)
            duplicate_state = upload_state(cdp)
            (EVIDENCE / "duplicate-upload-state.json").write_text(json.dumps(duplicate_state, indent=2), encoding="utf-8")
            duplicate_calls = [call for call in duplicate_state.get("fetch_calls", []) if "/api/v1/upload-processing-jobs" in call]
            duplicate_transaction_results_visible = "Transaction check results" in duplicate_state.get("body_text", "")
            duplicate_ok = (
                "already uploaded" in duplicate_state.get("body_text", "").lower()
                and not duplicate_calls
                and not duplicate_transaction_results_visible
            )
            append_raw(f"Duplicate upload duplicate message visible: {'PASSED' if 'already uploaded' in duplicate_state.get('body_text', '').lower() else 'FAILED'}")
            append_raw(f"Duplicate upload processing job calls: {len(duplicate_calls)}")
            append_raw(f"Duplicate upload transaction result panel visible: {'FAILED' if duplicate_transaction_results_visible else 'PASSED'}")
            shot = browser_screenshot(cdp, f"05-duplicate-terminal-{DATE}")
            rows.append(
                (
                    "Duplicate terminal state",
                    shot,
                    "Duplicate upload shows Document already uploaded with STATUS duplicate and does not continue to transaction checks.",
                    "Pass - duplicate stopped at M3/M4 boundary." if duplicate_ok else "Fail - duplicate did not prove the expected terminal behavior.",
                )
            )
            cdp.eval(
                """
                (() => {
                  const status = document.querySelector('#upload-state');
                  if (status) {
                    status.scrollIntoView({ block: 'center' });
                  }
                  return true;
                })()
                """
            )
            time.sleep(1)
            shot = browser_screenshot(cdp, f"06-duplicate-user-message-{DATE}")
            rows.append(
                (
                    "Duplicate user message",
                    shot,
                    "The visible upload status says this document was already uploaded.",
                    "Pass - user-facing duplicate message is visible." if "already uploaded" in duplicate_state.get("body_text", "").lower() else "Fail - duplicate message was not visible.",
                )
            )

            try:
                pytest_summary = run_targeted_pytest()
                append_raw("Container focused pytest: PASSED")
                append_raw(pytest_summary)
            except Exception as exc:
                pytest_summary = str(exc)
                append_raw("Container focused pytest: FAILED")
                append_raw(pytest_summary)
            result = "PASSED" if duplicate_ok and "FAILED" not in pytest_summary else "FAILED"
        else:
            append_raw("First upload queued: FAILED")
            append_raw("First upload UI state:")
            append_raw(json.dumps(first_state, indent=2))
            shot = browser_screenshot(cdp, f"04-first-upload-not-queued-{DATE}")
            rows.append(("First upload not queued", shot, "The real fixture upload state is visible after selecting the file.", "Fail - first upload did not reach queued, so duplicate flow was not valid to run."))
            try:
                pytest_summary = run_targeted_pytest()
                append_raw("Container focused pytest: PASSED")
                append_raw(pytest_summary)
            except Exception as exc:
                pytest_summary = str(exc)
                append_raw("Container focused pytest: FAILED")
                append_raw(pytest_summary)
            result = "FAILED"
    finally:
        cleanup_admin()
        if edge_process is not None:
            try:
                if cdp is not None:
                    cdp.call("Browser.close", timeout=5)
            except Exception:
                pass
            try:
                edge_process.terminate()
            except Exception:
                pass
        shutil.rmtree(PROFILE, ignore_errors=True)

    append_raw(f"Result: {result}")
    terminal_shot = capture_terminal_summary()
    rows.append(("Terminal result", terminal_shot, f"PowerShell shows raw flow output and final Result: {result}.", f"{result.title()} - terminal evidence captured."))
    write_evidence_docs(rows, first_state, duplicate_state, pytest_summary, result)
    return 0 if result == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
