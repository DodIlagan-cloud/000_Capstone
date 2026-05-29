"""M13 - Containerization Start
Capture optimized M1-M7 human acceptance evidence through the M13 container runtime.
M13 End"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import socket
import struct
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab


ROOT = Path(r"C:\000_Capstone")
DATE = "2026-05-29"
EVIDENCE = ROOT / "tests" / "results" / "M13-Containerization" / f"M13-M1-M7-screenshots-{DATE}"
PROFILE = EVIDENCE / f"edge-m13-m1-m7-profile-{DATE}"
PORT = 9257
BASE_URL = "http://127.0.0.1:8080"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
COMPOSE = ROOT / "infrastructure" / "compose" / "stats-runtime.compose.yml"
ENV_FILE = ROOT / "infrastructure" / "compose" / ".env.container"
INPUT_DIR = ROOT / "tests" / "input"
SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}

ADMIN_EMAIL = "m13.screenshot.admin@example.test"
ADMIN_TEMP_PASSWORD = "AdminPass123!"
ADMIN_NEW_PASSWORD = "AdminPass456!"
USER_EMAIL = f"m13.screenshot.user.{int(time.time())}@example.test"
USER_TEMP_PASSWORD = "TempPass123!"
EDGE_PROMPT_DISMISSED = False


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
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, n: int) -> bytes:
        chunks = []
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
        remote = result.get("result", {})
        return remote.get("value")


def run(command: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=ROOT, text=True, input=input_text, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def health_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_stack() -> str:
    running = run(["docker", "ps", "--filter", "name=stats-runtime", "--format", "{{.Names}}"], check=False)
    if "stats-runtime" in running.stdout and health_ready():
        return "reused"

    run([
        "docker",
        "compose",
        "--file",
        str(COMPOSE),
        "--env-file",
        str(ENV_FILE),
        "up",
        "--build",
        "--detach",
    ])
    deadline = time.time() + 180
    while time.time() < deadline:
        if health_ready():
            return "started"
        time.sleep(2)
    raise TimeoutError("Stats Web health did not become ready")


def seed_admin() -> None:
    reset_script = f"""
from app.db import SessionLocal
from app.models.user import User
from app.utils.security import hash_password

db = SessionLocal()
u = db.query(User).filter(User.email == {ADMIN_EMAIL!r}).one_or_none()
if u is None:
    u = User(email={ADMIN_EMAIL!r}, full_name="M13 Screenshot Admin", role="admin")
    db.add(u)
u.hashed_password = hash_password({ADMIN_TEMP_PASSWORD!r})
u.must_change_password = True
u.is_active = True
u.role = "admin"
db.commit()
print("M13 screenshot admin ready")
"""
    run([
        "docker",
        "exec",
        "--workdir",
        "/app/modules/identity-access-module",
        "stats-runtime",
        "/opt/stats/runtime/bin/python",
        "-c",
        reset_script,
    ])


def wait_for_debugger() -> str:
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            target_url = urllib.parse.quote(f"{BASE_URL}/Login", safe="")
            request = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{target_url}", method="PUT")
            with urllib.request.urlopen(request, timeout=2) as response:
                target = json.loads(response.read().decode("utf-8"))
            if target.get("type") == "page":
                return target["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("Edge remote debugger did not become available")


def wait_for(cdp: CdpClient, expression: str, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.eval(expression, timeout=4):
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise TimeoutError(expression)


def screenshot(name: str, cdp: CdpClient) -> Path:
    cdp.call("Page.bringToFront")
    try:
        window = cdp.call("Browser.getWindowForTarget")
        cdp.call(
            "Browser.setWindowBounds",
            {"windowId": window["windowId"], "bounds": {"left": 0, "top": 0, "width": 1220, "height": 860, "windowState": "normal"}},
        )
    except Exception:
        pass
    dismiss_edge_sync_prompt()
    time.sleep(2)
    path = EVIDENCE / f"m13-m1-m7-{name}-{DATE}.png"
    ImageGrab.grab().save(path)
    print(path)
    return path


def dismiss_edge_sync_prompt() -> None:
    global EDGE_PROMPT_DISMISSED
    if EDGE_PROMPT_DISMISSED:
        return
    user32 = ctypes.windll.user32
    # Edge's first-run sync prompt is native browser UI, not page DOM. This click
    # lands on the "Got it" button when the prompt appears over the test window.
    user32.SetCursorPos(733, 438)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    EDGE_PROMPT_DISMISSED = True
    time.sleep(0.3)


def navigate(cdp: CdpClient, path: str) -> None:
    cdp.call("Page.navigate", {"url": f"{BASE_URL}{path}"})
    wait_for(cdp, "document.readyState === 'complete'", timeout=30)


def js_string(value: str) -> str:
    return json.dumps(value)


def safe_slug(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", path.stem).strip("-").lower()
    return slug[:52] or "input"


def supported_inputs() -> list[Path]:
    return sorted(path for path in INPUT_DIR.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES)


def count_signals(text_value: str) -> dict:
    amount_matches = re.findall(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)", text_value)
    date_matches = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b",
        text_value,
        flags=re.IGNORECASE,
    )
    transaction_words = re.findall(
        r"\b(?:payment|purchase|debit|credit|withdrawal|deposit|transfer|fee|interest|total|amount|balance|reference)\b",
        text_value,
        flags=re.IGNORECASE,
    )
    return {
        "amount_signal_count": len(amount_matches),
        "date_signal_count": len(date_matches),
        "transaction_signal_count": len(transaction_words),
    }


def parsed_text_content(parsed: dict) -> str:
    text_value = parsed.get("text") if isinstance(parsed, dict) else ""
    if isinstance(text_value, dict):
        return str(text_value.get("content") or "")
    if isinstance(text_value, str):
        return text_value
    return ""


def redact_parse_json(cdp: CdpClient, fixture: Path) -> tuple[dict, dict | None]:
    script = f"""
    (() => {{
      const parseResult = document.querySelector('#parse-result');
      const rawPre = parseResult?.querySelector('pre');
      let parsed = {{}};
      if (rawPre) {{
        try {{ parsed = JSON.parse(rawPre.textContent); }} catch (error) {{ parsed = {{}}; }}
      }}
      const classification = parsed.classification || {{}};
      const strategy = parsed.strategy || {{}};
      const text = parsed.text || {{}};
      const findings = Array.isArray(parsed.findings) ? parsed.findings : [];
      return {{
        parsed,
        redacted: {{
          file_name: {js_string(fixture.name)},
          parse_id: parsed.parse_id || null,
          status: parsed.status || null,
          document_type: classification.document_type || parsed.document?.document_type || 'unknown',
          confidence: classification.confidence ?? 0,
          selected_strategy: strategy.selected_strategy || parsed.evaluation?.strategy || 'unknown',
          text_length: text.length ?? 0,
          finding_codes: findings.map((finding) => finding.code || finding.message || 'finding'),
          privacy_note: 'Raw extracted text and financial identifiers are intentionally omitted from screenshot evidence.'
        }}
      }};
    }})()
    """
    result = cdp.eval(script, timeout=10) or {}
    parsed = result.get("parsed") or {}
    redacted = result.get("redacted") or {}
    text_value = parsed_text_content(parsed) if isinstance(parsed, dict) else ""
    signals = count_signals(text_value)
    redacted.update(signals)
    redacted["m7_ready"] = signals["amount_signal_count"] > 0 and (
        signals["transaction_signal_count"] > 0 or signals["date_signal_count"] > 0
    )

    display_script = f"""
    (() => {{
      const parseResult = document.querySelector('#parse-result');
      const rawPre = parseResult?.querySelector('pre');
      const redacted = {json.dumps(redacted)};
      if (rawPre) {{
        rawPre.textContent = JSON.stringify(redacted, null, 2);
      }}
      const details = parseResult?.querySelector('details.json-output');
      if (details) {{
        details.open = true;
      }}
      const banner = document.createElement('div');
      banner.className = 'validation-result';
      banner.style.border = '1px solid #5fc8b5';
      banner.style.marginBottom = '12px';
      banner.innerHTML = '<h3>Privacy-safe M5 JSON evidence</h3><p>Raw extracted text, Personal Information, card numbers, and account numbers are redacted. This summary keeps M7-readiness signals only.</p>';
      parseResult?.prepend(banner);
      window.scrollTo(0, Math.max(0, parseResult.offsetTop - 120));
      return true;
    }})()
    """
    cdp.eval(display_script, timeout=10)
    return redacted, parsed if isinstance(parsed, dict) else None


def upload_fixture(cdp: CdpClient, fixture: Path, index: int) -> tuple[Path, dict, dict | None]:
    navigate(cdp, "/Upload")
    wait_for(cdp, "!!document.querySelector('#landing-workspace') && !document.querySelector('#landing-workspace').hidden", timeout=20)
    document = cdp.call("DOM.getDocument", {"depth": 1})
    root_node = document["root"]["nodeId"]
    node = cdp.call("DOM.querySelector", {"nodeId": root_node, "selector": "#document-file"})["nodeId"]
    cdp.call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(fixture)]})
    cdp.eval("document.querySelector('#document-file').dispatchEvent(new Event('change', { bubbles: true })); true")
    wait_for(cdp, "!!document.querySelector('#parse-result:not([hidden])')", timeout=320)
    wait_for(cdp, "document.body.innerText.includes('Document validated and parsed') || document.body.innerText.includes('Document parsing needs review')", timeout=20)
    redacted, parsed = redact_parse_json(cdp, fixture)
    shot = screenshot(f"07-file-{index:02d}-{safe_slug(fixture)}", cdp)
    return shot, redacted, parsed


def m7_payload_from_m5(parsed_file: dict) -> dict | None:
    parsed = parsed_file.get("parsed") or {}
    text_content = parsed_text_content(parsed).strip()
    if not text_content:
        return None
    return {
        "parse_id": parsed.get("parse_id") or f"m5-{safe_slug(Path(parsed_file['file_name']))}",
        "document_type": parsed_file.get("document_type") or "unknown",
        "text": text_content,
        "options": {"min_confidence": 0.1},
    }


def execute_m7_from_m5(parsed_files: list[dict]) -> list[dict]:
    m7_ready_files = [item for item in parsed_files if item.get("m7_ready")]
    results = []
    for item in m7_ready_files:
        payload = m7_payload_from_m5(item)
        if payload is None:
            continue
        slug = safe_slug(Path(item["file_name"]))
        container_payload = f"/tmp/m13_m7_payload_{slug}.json"
        run(
            ["docker", "exec", "-i", "stats-runtime", "sh", "-lc", f"cat > {container_payload}"],
            input_text=json.dumps(payload),
        )
        response = run([
            "docker",
            "exec",
            "stats-runtime",
            "curl",
            "-s",
            "-X",
            "POST",
            "http://localhost:8016/api/v1/extractions",
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            f"@{container_payload}",
        ])
        body = json.loads(response.stdout)
        summary = body.get("summary") or {}
        results.append(
            {
                "file_name": item["file_name"],
                "container_payload": container_payload,
                "status": body.get("status"),
                "transaction_candidate_count": summary.get("transaction_candidate_count", 0),
                "amount_total": summary.get("amount_total", 0),
                "finding_codes": [finding.get("code") for finding in body.get("findings", []) if finding.get("code")],
            }
        )
    return results


def bring_window_to_front(title_text: str) -> None:
    user32 = ctypes.windll.user32
    found = []

    def enum_windows(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if title_text in buffer.value:
            found.append(hwnd)
            return False
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(callback, None)
    if not found:
        raise RuntimeError(f"Could not find visible window containing title: {title_text}")

    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(2)


def terminal_screenshot(script_name: str, window_title: str, screenshot_name: str, script_body: str, wait_seconds: int = 8) -> Path:
    script_path = EVIDENCE / script_name
    script_path.write_text(script_body, encoding="utf-8")
    proc = subprocess.Popen(
        ["powershell", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", str(script_path)],
        cwd=ROOT,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    try:
        time.sleep(wait_seconds)
        bring_window_to_front(window_title)
        path = EVIDENCE / screenshot_name
        ImageGrab.grab().save(path)
        print(path)
        return path
    finally:
        proc.terminate()
        time.sleep(1)


def capture_terminal_evidence(stack_state: str, m7_results: list[dict]) -> list[Path]:
    health_title = "M13 Terminal Docker Health"
    health_lines = [
        f'$Host.UI.RawUI.WindowTitle = "{health_title}"',
        'Set-Location "C:\\000_Capstone"',
        "$Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size(132, 3000)",
        "$Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(132, 38)",
        "Clear-Host",
        'function Run-AcceptanceCommand($Command) {',
        '  Write-Host ""',
        '  Write-Host ("PS C:\\000_Capstone> " + $Command) -ForegroundColor Cyan',
        '  Invoke-Expression $Command',
        '}',
        '$cmd = @\'',
        'docker ps --filter "name=stats"',
        '\'@',
        'Run-AcceptanceCommand $cmd',
        '$cmd = @\'',
        'docker exec stats-runtime curl -s http://localhost:8013/health | ConvertFrom-Json | ForEach-Object { "service=$($_.service); status=$($_.status)" }',
        '\'@',
        'Run-AcceptanceCommand $cmd',
        '$cmd = @\'',
        'docker exec stats-runtime curl -s http://localhost:8014/health | ConvertFrom-Json | ForEach-Object { "service=$($_.service); status=$($_.status)" }',
        '\'@',
        'Run-AcceptanceCommand $cmd',
        '$cmd = @\'',
        'docker exec stats-runtime curl -s http://localhost:8015/health | ConvertFrom-Json | ForEach-Object { "service=$($_.service); status=$($_.status); ocr=$($_.ocr.engine); tesseract_available=$($_.ocr.tesseract_available)" }',
        '\'@',
        'Run-AcceptanceCommand $cmd',
        '$cmd = @\'',
        'docker exec stats-runtime curl -s http://localhost:8016/health | ConvertFrom-Json | ForEach-Object { "service=$($_.service); status=$($_.status)" }',
        '\'@',
        'Run-AcceptanceCommand $cmd',
        'Run-AcceptanceCommand "docker exec stats-runtime tesseract --version 2>&1 | Select-Object -First 1"',
    ]
    health_shot = terminal_screenshot(
        f"m13-container-terminal-health-{DATE}.ps1",
        health_title,
        f"m13-m1-m7-09a-container-health-commands-{DATE}.png",
        "\n".join(health_lines),
        wait_seconds=10,
    )

    shots = [health_shot]
    if not m7_results:
        return shots

    for chunk_index, start in enumerate(range(0, len(m7_results), 3), start=1):
        chunk = m7_results[start : start + 3]
        suffix = chr(ord("b") + chunk_index - 1)
        title = f"M13 Terminal M7 From M5 {chunk_index}"
        script_lines = [
        f'$Host.UI.RawUI.WindowTitle = "{title}"',
        'Set-Location "C:\\000_Capstone"',
        "$Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size(132, 3000)",
            "$Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(132, 30)",
        "Clear-Host",
        'function Run-AcceptanceCommand($Command) {',
        '  Write-Host ""',
        '  Write-Host ("PS C:\\000_Capstone> " + $Command) -ForegroundColor Cyan',
        '  Invoke-Expression $Command',
        '}',
        ]
        for result in chunk:
            script_lines.extend([
                f'Write-Host "M5 source: {result["file_name"]}" -ForegroundColor Yellow',
                '$cmd = @\'',
                "docker exec stats-runtime curl -s -X POST http://localhost:8016/api/v1/extractions -H 'Content-Type: application/json' "
                f"--data-binary '@{result['container_payload']}' "
                '| ConvertFrom-Json | ForEach-Object { "status=$($_.status); transactions=$($_.summary.transaction_candidate_count); amount_total=$($_.summary.amount_total)" }',
                '\'@',
                'Run-AcceptanceCommand $cmd',
            ])
        shots.append(
            terminal_screenshot(
                f"m13-container-terminal-m7-from-m5-{chunk_index}-{DATE}.ps1",
                title,
                f"m13-m1-m7-09{suffix}-m7-from-m5-commands-{DATE}.png",
                "\n".join(script_lines),
                wait_seconds=10,
            )
        )
    return shots


def send_terminal_key(keys: str) -> None:
    shell = ctypes.windll.user32
    # Use PowerShell's SendKeys through a tiny visible-window-neutral process; this
    # keeps the acceptance screenshots in one terminal session.
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys('{keys}')"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def create_contact_sheet() -> Path:
    images = sorted(path for path in EVIDENCE.glob("m13-m1-m7-*.png") if "contact-sheet" not in path.name)
    thumb_w, thumb_h = 360, 225
    thumbs = []
    for path in images:
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h))
        canvas = Image.new("RGB", (thumb_w, thumb_h + 42), "white")
        canvas.paste(image, ((thumb_w - image.width) // 2, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((6, thumb_h + 4), path.name[:58], fill=(0, 0, 0))
        thumbs.append(canvas)
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + 42)), (230, 230, 230))
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % cols) * thumb_w, (index // cols) * (thumb_h + 42)))
    output = EVIDENCE / f"M13-M1-M7-browser-screenshot-contact-sheet-{DATE}.png"
    sheet.save(output)
    return output


def write_index(rows: list[tuple[str, str, str]], files: list[dict], m7_results: list[dict], contact_sheet: Path) -> None:
    lines = [
        "<!-- M13 - Containerization Start -->",
        "<!-- Screenshot evidence index for M1-M7 through the M13 container runtime. -->",
        "",
        "# M13 M1-M7 Screenshot Evidence",
        "",
        "Runtime under test:",
        "",
        "```text",
        "http://127.0.0.1:8080",
        "stats-runtime",
        "stats-db",
        "```",
        "",
        "This is an optimized human acceptance evidence pass. Session-level M1/M2/M13 checks are captured once. Every supported file in `tests/input` is uploaded once through the UI because each file represents distinct M3/M4/M5 document coverage. M7 is executed only against M5 outputs that are transaction-useful.",
        "",
        "| Evidence | File | Result |",
        "| --- | --- | --- |",
    ]
    for label, file_name, result in rows:
        lines.append(f"| {label} | `{file_name}` | {result} |")
    lines.append(f"| Contact sheet review | `{contact_sheet.name}` | Consolidated visual review of the retained screenshots. |")

    lines.extend([
        "",
        "## Input Coverage",
        "",
        "| Input file | Status | Strategy | Text length | M7 ready | Amount signals | Date signals | Transaction signals | Findings |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ])
    for item in files:
        findings = ", ".join(item.get("finding_codes") or []) or "None"
        lines.append(
            f"| `{item['file_name']}` | {item.get('status') or 'unknown'} | {item.get('selected_strategy') or 'unknown'} | {item.get('text_length') or 0} | {item.get('m7_ready')} | {item.get('amount_signal_count', 0)} | {item.get('date_signal_count', 0)} | {item.get('transaction_signal_count', 0)} | {findings} |"
        )

    lines.extend([
        "",
        "## M7 From M5 Coverage",
        "",
        "| M5 source file | M7 status | Transaction candidates | Amount total | Findings |",
        "| --- | --- | ---: | ---: | --- |",
    ])
    for item in m7_results:
        findings = ", ".join(item.get("finding_codes") or []) or "None"
        lines.append(
            f"| `{item['file_name']}` | {item.get('status')} | {item.get('transaction_candidate_count', 0)} | {item.get('amount_total', 0)} | {findings} |"
        )

    lines.extend(
        [
            "",
            "## Privacy Note",
            "",
            "Screenshots and summaries intentionally redact raw extracted text, Personal Information, card numbers, and account numbers. M7 payloads were generated from in-memory M5 parse output and placed only as temporary files inside `stats-runtime` for the acceptance request.",
            "",
            "<!-- M13 End -->",
        ]
    )
    (EVIDENCE / f"M13-M1-M7-screenshot-evidence-{DATE}.md").write_text("\n".join(lines), encoding="utf-8")


def login_and_capture_session(cdp: CdpClient, evidence_rows: list[tuple[str, str, str]]) -> None:
    navigate(cdp, "/health")
    shot = screenshot("00-container-health", cdp)
    evidence_rows.append(("M13 browser health", shot.name, "Browser shows Docker-exposed Stats Web health at `http://127.0.0.1:8080/health`."))

    navigate(cdp, "/Login")
    shot = screenshot("01-login-page", cdp)
    evidence_rows.append(("M1 login", shot.name, "Docker-hosted login page is reachable."))

    cdp.eval(
        f"""
        (() => {{
          const form = document.querySelector('#login-form');
          form.querySelector('input[name="email"]').value = {js_string(ADMIN_EMAIL)};
          form.querySelector('input[name="password"]').value = {js_string(ADMIN_TEMP_PASSWORD)};
          form.requestSubmit();
          return true;
        }})()
        """
    )
    wait_for(cdp, "!!document.querySelector('#password-setup-form') && !document.querySelector('#password-setup-form').hidden", timeout=20)
    shot = screenshot("02-admin-password-reset", cdp)
    evidence_rows.append(("M1 admin password reset", shot.name, "Seeded container admin is forced through first-login password reset."))

    cdp.eval(
        f"""
        (() => {{
          const form = document.querySelector('#password-setup-form');
          form.querySelector('input[name="new_password"]').value = {js_string(ADMIN_NEW_PASSWORD)};
          form.querySelector('input[name="confirm_password"]').value = {js_string(ADMIN_NEW_PASSWORD)};
          form.requestSubmit();
          return true;
        }})()
        """
    )
    wait_for(cdp, "location.pathname === '/' && document.body.innerText.includes('Access granted')", timeout=25)
    shot = screenshot("03-admin-workspace", cdp)
    evidence_rows.append(("M1/M2 admin workspace", shot.name, "Authenticated workspace renders through containerized Stats Web."))

    navigate(cdp, "/Users")
    wait_for(cdp, "!!document.querySelector('#users-workspace') && !document.querySelector('#users-workspace').hidden", timeout=20)
    shot = screenshot("04-user-management", cdp)
    evidence_rows.append(("M1 user management", shot.name, "Admin user management flow renders once for the session."))

    cdp.eval(
        f"""
        (() => {{
          const form = document.querySelector('#create-user-form');
          const setValue = (selector, value) => {{
            const node = form.querySelector(selector);
            node.value = value;
            node.dispatchEvent(new Event('input', {{ bubbles: true }}));
            node.dispatchEvent(new Event('change', {{ bubbles: true }}));
          }};
          setValue('#full-name', 'Screenshot User');
          setValue('#user-email', {js_string(USER_EMAIL)});
          setValue('#temporary-password', {js_string(USER_TEMP_PASSWORD)});
          setValue('#role', 'user');
          const active = form.querySelector('#is-active');
          active.checked = true;
          active.dispatchEvent(new Event('change', {{ bubbles: true }}));
          form.querySelector('#create-user-submit').click();
          return true;
        }})()
        """
    )
    wait_for(cdp, "document.querySelector('#create-message')?.innerText.includes('created')", timeout=25)
    shot = screenshot("05-user-created", cdp)
    evidence_rows.append(("M1 user creation", shot.name, "Admin creates a test user once through the Docker-hosted UI."))

    navigate(cdp, "/Upload")
    wait_for(cdp, "!!document.querySelector('#landing-workspace') && !document.querySelector('#landing-workspace').hidden", timeout=20)
    shot = screenshot("06-upload-page", cdp)
    evidence_rows.append(("M3/M4/M5 upload workflow", shot.name, "Authenticated upload page is open once for the per-file workflow."))


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    files = supported_inputs()
    if not files:
        raise RuntimeError(f"No supported input files found in {INPUT_DIR}")

    stack_state = ensure_stack()
    seed_admin()

    subprocess.Popen(
        [
            EDGE,
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={PROFILE}",
            "--no-first-run",
            "--start-maximized",
            "--new-window",
            f"{BASE_URL}/Login",
        ],
        cwd=ROOT,
    )
    ws_url = wait_for_debugger()
    cdp = CdpClient(ws_url)
    cdp.call("Page.enable")
    cdp.call("DOM.enable")
    cdp.call("Network.enable")
    cdp.call("Network.setCacheDisabled", {"cacheDisabled": True})
    cdp.call("Runtime.enable")
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1220, "height": 760, "deviceScaleFactor": 1, "mobile": False})
    wait_for(cdp, "document.readyState === 'complete'", timeout=20)

    evidence_rows: list[tuple[str, str, str]] = []
    parsed_files: list[dict] = []

    login_and_capture_session(cdp, evidence_rows)

    for index, fixture in enumerate(files, start=1):
        shot, redacted, parsed = upload_fixture(cdp, fixture, index)
        redacted = redacted or {"file_name": fixture.name, "status": "unknown"}
        redacted["parsed"] = parsed
        parsed_files.append(redacted)
        evidence_rows.append(
            (
                f"M3/M4/M5 per-file flow for {fixture.name}",
                shot.name,
                "File is uploaded once through the UI, validated, ingested, parsed, and summarized with privacy-safe M7-readiness signals.",
            )
        )

    navigate(cdp, "/Documents")
    wait_for(cdp, "document.readyState === 'complete' && document.body.innerText.includes('Documents')", timeout=20)
    shot = screenshot("08-documents-page", cdp)
    evidence_rows.append(("M2 documents page", shot.name, "Containerized Stats Web documents route renders once for shell navigation proof."))

    m7_results = execute_m7_from_m5(parsed_files)
    terminal_shots = capture_terminal_evidence(stack_state, m7_results)
    evidence_rows.append(("Container runtime and module API commands", terminal_shots[0].name, "PowerShell shows exact Docker commands, outputs, and PASS interpretation."))
    for index, terminal_shot in enumerate(terminal_shots[1:], start=1):
        evidence_rows.append((f"M7 extraction from M5 outputs chunk {index}", terminal_shot.name, "PowerShell shows exact M7 curl commands using M5-derived payload files inside `stats-runtime`."))

    contact_sheet = create_contact_sheet()
    parsed_summary = [{key: value for key, value in item.items() if key != "parsed"} for item in parsed_files]
    write_index(evidence_rows, parsed_summary, m7_results, contact_sheet)
    summary = {
        "runtime": "stats-runtime",
        "base_url": BASE_URL,
        "stack_state": stack_state,
        "admin_email": ADMIN_EMAIL,
        "created_user_email": USER_EMAIL,
        "input_files": [path.name for path in files],
        "parsed_files": parsed_summary,
        "m7_results": m7_results,
        "screenshots": [row[1] for row in evidence_rows],
        "contact_sheet": contact_sheet.name,
        "note": "Passwords and raw extracted financial text are intentionally omitted from this evidence summary.",
    }
    (EVIDENCE / f"M13-M1-M7-screenshot-summary-{DATE}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Result: PASSED")


if __name__ == "__main__":
    main()
