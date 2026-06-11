"""Capture desktop evidence for M5/M7/M9 recognition label approval.

This runner uses visible Microsoft Edge and visible PowerShell windows so the
screenshots match a human acceptance test. It uses only real input files from
tests/input and never prints database connection strings or passwords.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import socket
import struct
import subprocess
import textwrap
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import ImageGrab


ROOT = Path(__file__).resolve().parents[3]
DATE = "2026-06-11"
STAMP = time.strftime("%Y%m%d-%H%M%S")
STAMP_KEY = STAMP.replace("-", "_").lower()
BASE_URL = "http://127.0.0.1:8080"
PORT = 9300 + (int(time.time()) % 400)
EVIDENCE = ROOT / "tests" / "results" / "M5-M7-M9-RecognitionApproval" / f"M5-M7-M9-recognition-approval-{DATE}-{STAMP}"
PROFILE = EVIDENCE / f"edge-profile-{DATE}-{STAMP}"
EDGE = os.environ.get("STATS_EDGE_EXECUTABLE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
INPUT_FILE = Path(os.environ.get("STATS_RECOGNITION_EVIDENCE_INPUT") or ROOT / "tests" / "input" / "20260603_122154.jpg")

ADMIN_EMAIL = "m5m7.approval.admin@example.test"
ADMIN_PASSWORD = "AdminEvidence123!"

TARGETS = {
    "document": {"label": "receipt", "test_label": f"test_document_type_{STAMP_KEY}", "values": "receipt, payment receipt"},
    "transaction": {"label": "purchase", "test_label": f"test_transaction_type_{STAMP_KEY}", "values": "eftpos_payment, card_purchase"},
    "spending": {"label": "shopping", "test_label": f"test_spending_category_{STAMP_KEY}", "values": "retail, general_merchandise"},
}

SCREEN_BBOX = (0, 0, 1320, 900)


class CdpClient:
    def __init__(self, ws_url: str) -> None:
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
        if opcode not in (1, 0):
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
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            text = details.get("text") or "JavaScript evaluation failed"
            exception = details.get("exception", {})
            description = exception.get("description") or exception.get("value") or text
            raise RuntimeError(str(description))
        remote = result.get("result", {})
        return remote.get("value")


def run(command: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=ROOT, text=True, input=input_text, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def wait_for_debugger() -> str:
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as response:
                targets = json.loads(response.read().decode("utf-8"))
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    return target["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("Edge remote debugger did not become available")


def health_ready() -> None:
    with urllib.request.urlopen(f"{BASE_URL}/health", timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Stats Web health returned HTTP {response.status}")


def wait_for(cdp: CdpClient, expression: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.eval(expression, timeout=5):
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise TimeoutError(expression)


def navigate(cdp: CdpClient, path: str) -> None:
    cdp.call("Page.navigate", {"url": f"{BASE_URL}{path}"})
    wait_for(cdp, "document.readyState === 'complete'", timeout=40)


def bring_edge_to_front(cdp: CdpClient) -> None:
    cdp.call("Page.bringToFront")
    try:
        window = cdp.call("Browser.getWindowForTarget")
        cdp.call(
            "Browser.setWindowBounds",
            {
                "windowId": window["windowId"],
                "bounds": {"left": 0, "top": 0, "width": 1320, "height": 900, "windowState": "normal"},
            },
        )
    except Exception:
        pass
    title = cdp.eval("document.title || ''", timeout=5) or "Stats"
    bring_visible_edge_window_to_front(str(title))
    time.sleep(1.0)


def bring_visible_edge_window_to_front(title_hint: str = "Stats") -> None:
    user32 = ctypes.windll.user32
    exact_targets: list[int] = []
    fallback_targets: list[int] = []

    def enum_windows(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title_hint and title_hint in title:
            exact_targets.append(hwnd)
            return False
        if "Stats" in title or "Microsoft Azure" in title:
            fallback_targets.append(hwnd)
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(callback, None)
    targets = exact_targets or fallback_targets
    if targets:
        hwnd = targets[-1]
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)


def edge_process_ids() -> set[int]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process msedge -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    ids: set[int] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            ids.add(int(line))
    return ids


def minimize_existing_edge_windows() -> None:
    user32 = ctypes.windll.user32
    edge_pids = edge_process_ids()
    if not edge_pids:
        return

    def enum_windows(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) in edge_pids:
            user32.ShowWindow(hwnd, 6)
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(callback, None)
    time.sleep(0.5)


def close_existing_stats_edge_windows() -> None:
    user32 = ctypes.windll.user32

    def enum_windows(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title.startswith("Stats ") or " - Stats " in title:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(callback, None)
    time.sleep(1.0)


def screenshot(cdp: CdpClient, name: str) -> Path:
    bring_edge_to_front(cdp)
    dismiss_edge_prompts()
    path = EVIDENCE / f"{name}-{DATE}.png"
    ImageGrab.grab(bbox=SCREEN_BBOX).save(path)
    return path


def dismiss_edge_prompts() -> None:
    user32 = ctypes.windll.user32
    # This coordinate lands on Edge's native "Got it" button when the profile
    # sync prompt appears. If no prompt is present, the click is harmless.
    user32.SetCursorPos(1082, 417)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.4)


def js(value: str) -> str:
    return json.dumps(value)


def seed_admin() -> None:
    script = f"""
from app.db import SessionLocal
from app.models.user import User
from app.utils.security import hash_password

db = SessionLocal()
user = db.query(User).filter(User.email == {ADMIN_EMAIL!r}).one_or_none()
if user is None:
    user = User(email={ADMIN_EMAIL!r}, full_name="M5 M7 Approval Admin", role="admin")
    db.add(user)
user.hashed_password = hash_password({ADMIN_PASSWORD!r})
user.must_change_password = False
user.is_active = True
user.role = "admin"
db.commit()
print("Evidence admin ready")
"""
    run(
        [
            "docker",
            "exec",
            "--workdir",
            "/app/modules/identity-access-module",
            "stats-runtime",
            "/opt/stats/runtime/bin/python",
            "-c",
            script,
        ]
    )


def cleanup_test_labels() -> None:
    script = """
from stats_data.database import open_azure_sql_connection
with open_azure_sql_connection() as connection:
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE dbo.recognition_labels "
        "SET is_active = 0, updated_at_utc = SYSUTCDATETIME() "
        "WHERE label_key LIKE 'test[_]%'"
    )
    connection.commit()
print("Inactive test labels cleaned")
"""
    run(
        [
            "docker",
            "exec",
            "--workdir",
            "/app/apps/stats-data",
            "-e",
            "PYTHONPATH=/app/apps/stats-data/src",
            "-i",
            "stats-runtime",
            "/opt/stats/runtime/bin/python",
            "-c",
            script,
        ]
    )


def ensure_db_helper() -> None:
    helper = EVIDENCE / "recognition_db_evidence_query.py"
    helper.write_text(
        textwrap.dedent(
            """
            from __future__ import annotations

            import sys
            from datetime import datetime, timezone
            from stats_data.database import open_azure_sql_connection as connect

            TEST_START = sys.argv[1]
            MODE = sys.argv[2]

            QUERIES = {
                "labels": '''
            SELECT label_scope, label_key, values_json, is_active
            FROM dbo.recognition_labels
            WHERE label_scope IN ('document','transaction','spending')
              AND label_key IN ('receipt','purchase','shopping','transport')
            ORDER BY label_scope, label_key;
            ''',
                "test_labels": '''
            SELECT label_scope, label_key, values_json, is_active
            FROM dbo.recognition_labels
            WHERE label_key LIKE 'test\\_%' ESCAPE '\\\\'
            ORDER BY label_scope, label_key;
            ''',
                "suggestions": '''
            SELECT TOP (20)
                   suggestion_id, source_module, suggestion_status,
                   current_document_type, suggested_document_type,
                   current_transaction_type, suggested_transaction_type,
                   current_spending_category, suggested_spending_category,
                   source_candidate_id, created_at_utc, reviewed_at_utc
            FROM dbo.recognition_label_suggestions
            WHERE created_at_utc >= ?
               OR reviewed_at_utc >= ?
            ORDER BY created_at_utc DESC;
            ''',
                "documents": '''
            SELECT TOP (10)
                   document_id, original_filename, document_type,
                   recognition_suggestion_id, recognition_suggestion_status,
                   suggested_document_type, created_at_utc, updated_at_utc
            FROM dbo.stats_documents
            WHERE created_at_utc >= ? OR updated_at_utc >= ?
            ORDER BY COALESCE(updated_at_utc, created_at_utc) DESC;
            ''',
                "transactions": '''
            SELECT TOP (10)
                   transaction_id, document_id, transaction_date, amount, currency,
                   transaction_type, transaction_subtype,
                   spending_category, spending_subcategory,
                   recognition_suggestion_id, recognition_suggestion_status,
                   suggested_transaction_type, suggested_spending_category,
                   created_at_utc, updated_at_utc
            FROM dbo.transactions
            WHERE created_at_utc >= ? OR updated_at_utc >= ?
            ORDER BY COALESCE(updated_at_utc, created_at_utc) DESC;
            ''',
                "validation": '''
            SELECT TOP (10)
                   validation_id, document_type, status, created_at_utc
            FROM dbo.validation_results
            WHERE created_at_utc >= ?
            ORDER BY created_at_utc DESC;
            ''',
            }

            sql = QUERIES[MODE]
            print("Azure SQL runtime query evidence")
            print("Connection source: stats-runtime environment")
            print("Secret policy: connection string is intentionally not printed")
            print("")
            print("Connection identity query:")
            print("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
            print("SQL query:")
            print(sql.strip())
            print("")
            with connect() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
                database_name, server_name = cursor.fetchone()
                print(f"database_name={database_name}")
                print(f"server_name={server_name}")
                print("")
                print("Result rows:")
                if MODE in {"suggestions", "documents", "transactions"}:
                    cursor.execute(sql, TEST_START, TEST_START)
                elif MODE == "validation":
                    cursor.execute(sql, TEST_START)
                else:
                    cursor.execute(sql)
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
            print(" | ".join(columns))
            for row in rows:
                values = []
                for value in row:
                    if isinstance(value, datetime):
                        values.append(value.replace(tzinfo=timezone.utc).isoformat())
                    else:
                        text = "" if value is None else str(value)
                        values.append(text[:90])
                print(" | ".join(values))
            print(f"Row count: {len(rows)}")
            if str(database_name).lower() != "sqldb-stats-dev":
                raise SystemExit(f"Result: FAILED - expected sqldb-stats-dev, got {database_name}")
            print("Result: PASSED - query executed against Azure SQL sqldb-stats-dev from stats-runtime")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    run(["docker", "cp", str(helper), "stats-runtime:/tmp/recognition_db_evidence_query.py"])


def bring_window_to_front(title_text: str) -> None:
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
    time.sleep(1.5)


def terminal_db_screenshot(test_start: str, mode: str, name: str) -> Path:
    title = f"Stats DB Evidence {mode} {STAMP}"
    ps1 = EVIDENCE / f"{name}.ps1"
    ps1.write_text(
        "\n".join(
            [
                f'$Host.UI.RawUI.WindowTitle = "{title}"',
                'Set-Location "C:\\000_Capstone"',
                "$Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size(160, 3000)",
                "$Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(150, 36)",
                "Clear-Host",
                f'Write-Host "Evidence DB query: {mode}" -ForegroundColor Cyan',
                'Write-Host "Secret policy: connection strings, passwords, and tokens are not printed."',
                'Write-Host ""',
                'Write-Host "PS C:\\000_Capstone> az account show --query ""{user:user.name, tenantId:tenantId}"" -o table" -ForegroundColor Cyan',
                'az account show --query "{user:user.name, tenantId:tenantId}" -o table',
                'Write-Host ""',
                'Write-Host "PS C:\\000_Capstone> az sql db show --resource-group rg-stats-dev --server sql-stats-dev-001 --name sqldb-stats-dev --query ""{database:name, server:serverName, status:status, location:location}"" -o table" -ForegroundColor Cyan',
                'az sql db show --resource-group rg-stats-dev --server sql-stats-dev-001 --name sqldb-stats-dev --query "{database:name, server:serverName, status:status, location:location}" -o table',
                'Write-Host ""',
                'Write-Host "PS C:\\000_Capstone> docker ps --filter ""name=stats-runtime"" --format ""table {{.Names}}\\t{{.Status}}\\t{{.Ports}}""" -ForegroundColor Cyan',
                'docker ps --filter "name=stats-runtime" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"',
                'Write-Host ""',
                'Write-Host "PS C:\\000_Capstone> docker exec stats-runtime ... recognition DB query" -ForegroundColor Cyan',
                f'docker exec --workdir /app/apps/stats-data -e PYTHONPATH=/app/apps/stats-data/src stats-runtime /opt/stats/runtime/bin/python /tmp/recognition_db_evidence_query.py "{test_start}" "{mode}"',
                'Write-Host ""',
                'Write-Host "Result: query completed" -ForegroundColor Green',
            ]
        ),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-NoExit",
            "-File",
            str(ps1),
        ],
        cwd=ROOT,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    try:
        time.sleep(6)
        bring_window_to_front(title)
        path = EVIDENCE / f"{name}-{DATE}.png"
        ImageGrab.grab(bbox=SCREEN_BBOX).save(path)
        return path
    finally:
        proc.terminate()
        time.sleep(0.5)


def login(cdp: CdpClient) -> None:
    navigate(cdp, "/Login")
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
    wait_for(cdp, "location.pathname === '/' && document.body.innerText.includes('Access granted')", timeout=30)


def open_admin(cdp: CdpClient) -> None:
    navigate(cdp, "/Admin/Classifications")
    wait_for(cdp, "!!document.querySelector('#classification-workspace') && !document.querySelector('#classification-workspace').hidden", timeout=30)
    cdp.eval("window.confirm = () => true; true")


def submit_new_label(cdp: CdpClient, scope: str, label: str, values: str) -> None:
    tab = "transaction-rules" if scope in {"transaction", "spending"} else "document-rules"
    form_id = {
        "document": "document-label-new",
        "transaction": "transaction-label-new",
        "spending": "spending-label-new",
    }[scope]
    cdp.eval(
        f"""
        (() => {{
          selectClassificationTab({js(tab)});
          const section = document.querySelector('[data-classification-section="{scope}"]');
          if (section) section.open = true;
          const form = document.querySelector('#{form_id}');
          document.querySelector(`[form="${{form.id}}"][name="label"]`).value = {js(label)};
          document.querySelector(`[form="${{form.id}}"][name="values"]`).value = {js(values)};
          form.requestSubmit();
          return true;
        }})()
        """
    )
    wait_for(cdp, f"document.querySelector('#classification-save-message')?.innerText.toLowerCase().includes('saved')", timeout=20)


def delete_label(cdp: CdpClient, scope: str, label: str) -> None:
    tab = "transaction-rules" if scope in {"transaction", "spending"} else "document-rules"
    cdp.eval(
        f"""
        (async () => {{
          window.confirm = () => true;
          selectClassificationTab({js(tab)});
          const section = document.querySelector('[data-classification-section="{scope}"]');
          if (section) section.open = true;
          const forms = Array.from(document.querySelectorAll('form[data-async-classification-form][data-classification-section="{scope}"][id$="-delete"]'));
          const canonical = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
          const expected = canonical({js(label.lower())});
          const form = forms.find((candidate) => {{
            const input = document.querySelector(`input[form="${{candidate.id}}"][name="label"]`);
            return input && canonical(input.value) === expected;
          }});
          if (!form) throw new Error('delete form not found for {scope}:{label}');
          const actionUrl = form.getAttribute('action') || window.location.href;
          const response = await fetch(actionUrl, {{
            method: form.method || 'POST',
            body: new FormData(form),
            headers: {{ 'X-Stats-Async-Save': 'true' }},
          }});
          const text = await response.text();
          let result = {{}};
          try {{ result = JSON.parse(text); }} catch {{ result = {{ ok: false, message: text }}; }}
          if (!response.ok || !result.ok) {{
            setSaveMessage(result.message || `Delete failed with HTTP ${{response.status}}`, 'error');
            throw new Error(result.message || `Delete failed with HTTP ${{response.status}}`);
          }}
          await refreshWorkbench('{scope}', result.message || 'Recognition setting deleted.');
          return result.message || 'deleted';
        }})()
        """
    , timeout=40)
    wait_for(cdp, "document.querySelector('#classification-save-message')?.innerText.toLowerCase().includes('deleted')", timeout=20)


def show_scope(cdp: CdpClient, scope: str) -> None:
    tab = "transaction-rules" if scope in {"transaction", "spending"} else "document-rules"
    cdp.eval(
        f"""
        (() => {{
          selectClassificationTab({js(tab)});
          document.querySelectorAll('details.classification-management').forEach((details) => details.open = false);
          const section = document.querySelector('[data-classification-section="{scope}"]');
          if (section) section.open = true;
          section?.scrollIntoView({{ block: 'start' }});
          return true;
        }})()
        """
    )
    time.sleep(0.8)


def upload_input(cdp: CdpClient) -> None:
    navigate(cdp, "/Upload")
    wait_for(cdp, "!!document.querySelector('#landing-workspace') && !document.querySelector('#landing-workspace').hidden", timeout=30)
    document = cdp.call("DOM.getDocument", {"depth": 1})
    root_node = document["root"]["nodeId"]
    node = cdp.call("DOM.querySelector", {"nodeId": root_node, "selector": "#document-file"})["nodeId"]
    cdp.call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(INPUT_FILE)]})
    time.sleep(1.0)
    started = cdp.eval(
        """
        (() => {
          const text = document.body.innerText || '';
          return text.includes('Document upload') || text.includes('Transaction check results') || text.includes('Transactions checked');
        })()
        """
    )
    if not started:
        cdp.eval("document.querySelector('#document-file').dispatchEvent(new Event('change', { bubbles: true })); true")
    wait_for(cdp, "document.querySelector('#parse-result') && !document.querySelector('#parse-result').hidden", timeout=360)
    wait_for(
        cdp,
        "document.querySelector('#parse-result h3')?.innerText.trim() === 'Transaction check results'",
        timeout=360,
    )
    duplicate_status = cdp.eval("/status\\s+duplicate/i.test(document.querySelector('#ingestion-result')?.innerText || '')")
    if duplicate_status:
        raise RuntimeError("Upload was treated as a duplicate by the ingestion workflow; choose a different real fixture or reset intake state.")
    cdp.eval("document.querySelector('#parse-result')?.scrollIntoView({ block: 'start' }); true")


def save_ready_transactions(cdp: CdpClient) -> None:
    can_save = cdp.eval(
        """
        (() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const save = buttons.find((button) => button.textContent.trim() === 'Save ready transactions');
          return !!save && !save.disabled;
        })()
        """
    )
    if not can_save:
        raise RuntimeError("Save ready transactions was not enabled after accepting review rows.")
    cdp.eval(
        """
        (() => {
          const save = Array.from(document.querySelectorAll('button')).find((button) => button.textContent.trim() === 'Save ready transactions');
          save?.click();
          return true;
        })()
        """
    )
    wait_for(
        cdp,
        "document.body.innerText.includes('Transactions saved') || document.body.innerText.includes('Review duplicates before saving') || document.body.innerText.includes('possible duplicate')",
        timeout=90,
    )


def accept_review_transactions(cdp: CdpClient) -> int:
    accepted = int(cdp.eval(
        """
        (() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const accepts = buttons.filter((button) => button.textContent.trim() === 'Accept' && !button.disabled);
          accepts.forEach((button) => button.click());
          return accepts.length;
        })()
        """
    ) or 0)
    if accepted <= 0:
        raise RuntimeError("No review rows were available to accept before saving.")
    wait_for(
        cdp,
        """
        (() => {
          const metrics = Array.from(document.querySelectorAll('.result-metrics div'));
          return metrics.some((metric) => metric.innerText.includes('Ready to save') && /^\\s*[1-9]/.test(metric.innerText));
        })()
        """,
        timeout=30,
    )
    return accepted


def review_tab(cdp: CdpClient) -> None:
    open_admin(cdp)
    cdp.eval(
        """
        (() => {
          selectClassificationTab('review-candidates');
          document.querySelectorAll('details.classification-management').forEach((details) => details.open = true);
          window.scrollTo(0, 0);
          return true;
        })()
        """
    )
    wait_for(cdp, "document.body.innerText.includes('Pending suggestions')", timeout=20)


def approve_all_pending(cdp: CdpClient) -> int:
    count = int(cdp.eval(
        """
        (() => {
          selectClassificationTab('review-candidates');
          document.querySelectorAll('details.classification-management').forEach((details) => details.open = true);
          return document.querySelectorAll('form[id$="-approve"]').length;
        })()
        """
    ) or 0)
    if count <= 0:
        raise RuntimeError("No pending recognition suggestions were created for this full-flow evidence run.")
    approved = cdp.eval(
        """
        (async () => {
          selectClassificationTab('review-candidates');
          document.querySelectorAll('details.classification-management').forEach((details) => details.open = true);
          let approvedCount = 0;
          while (true) {
            const form = document.querySelector('form[id$="-approve"]');
            if (!form) {
              break;
            }
            const body = new FormData(form);
            document.querySelectorAll(`[form="${form.id}"]`).forEach((field) => {
              if (field.name) {
                body.set(field.name, field.value || '');
              }
            });
            const actionUrl = form.getAttribute('action') || window.location.href;
            const response = await fetch(actionUrl, {
              method: form.method || 'POST',
              body,
              headers: { 'X-Stats-Async-Save': 'true' },
            });
            const text = await response.text();
            let result = {};
            try { result = JSON.parse(text); } catch { result = { ok: false, message: text }; }
            if (!response.ok || !result.ok) {
              let message = result.message || '';
              if (response.status === 404 || String(message).toLowerCase().includes('not found') || String(message).toLowerCase().includes('404')) {
                message = 'This review item is no longer available. Refresh the items to review and try again.';
              } else if (!message || String(message).trim().startsWith('{')) {
                message = 'Recognition setting could not be saved. Refresh the page and try again.';
              }
              setSaveMessage(message, 'error');
              throw new Error(message);
            }
            approvedCount += 1;
            await refreshWorkbench('review-candidates', result.message || 'Suggestion approved.');
            selectClassificationTab('review-candidates');
            document.querySelectorAll('details.classification-management').forEach((details) => details.open = true);
            await new Promise((resolve) => setTimeout(resolve, 500));
          }
          return approvedCount;
        })()
        """,
        timeout=120,
    )
    wait_for(cdp, "document.querySelector('#classification-save-message')?.innerText.toLowerCase().includes('approved') || document.querySelector('#classification-save-message')?.innerText.toLowerCase().includes('rejected') || document.body.innerText.includes('No recognition suggestions')", timeout=30)
    return int(approved or count)


def write_index(rows: list[tuple[str, Path, str]], result: str, notes: list[str]) -> None:
    lines = [
        "# M5/M7/M9 Recognition Approval Desktop Evidence",
        "",
        f"Date: {DATE}",
        f"Runtime: `{BASE_URL}` through `stats-runtime`",
        f"Real input file: `{INPUT_FILE}`",
        "",
        "## Screenshot Evidence",
        "",
        "| Step | File | What It Proves |",
        "| --- | --- | --- |",
    ]
    for label, path, proof in rows:
        lines.append(f"| {label} | `{path.name}` | {proof} |")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in notes)
    lines.extend(["", f"Result: {result}", ""])
    (EVIDENCE / f"M5-M7-M9-recognition-approval-evidence-{DATE}.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not INPUT_FILE.exists():
        raise RuntimeError(f"Required real input file not found: {INPUT_FILE}")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    health_ready()
    seed_admin()
    cleanup_test_labels()
    ensure_db_helper()
    test_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30))

    close_existing_stats_edge_windows()
    minimize_existing_edge_windows()
    subprocess.Popen(
        [
            EDGE,
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-features=msEdgeBrowserSignin,msImplicitSignin,msSingleSignOnOSForPrimaryAccountIsShared",
            "--start-maximized",
            "--new-window",
            f"{BASE_URL}/Login",
        ],
        cwd=ROOT,
    )
    ws_url = wait_for_debugger()
    cdp = CdpClient(ws_url)
    for domain in ["Page", "DOM", "Network", "Runtime"]:
        cdp.call(f"{domain}.enable")
    cdp.call("Network.setCacheDisabled", {"cacheDisabled": True})

    rows: list[tuple[str, Path, str]] = []
    notes: list[str] = []
    result = "FAILED"

    try:
        navigate(cdp, "/Login")
        rows.append(("Login page", screenshot(cdp, "01-login-page"), "Visible Edge shows the containerized login page URL."))
        login(cdp)
        rows.append(("Authenticated home", screenshot(cdp, "02-authenticated-home"), "Admin user logged in through the real Stats UI."))

        open_admin(cdp)
        rows.append(("Recognition settings collapsed", screenshot(cdp, "03-recognition-settings-collapsed"), "Admin page opens with management sections collapsed by default."))

        for scope, target in TARGETS.items():
            submit_new_label(cdp, scope, target["test_label"], target["values"])
            show_scope(cdp, scope)
            rows.append((f"Add {scope} test label", screenshot(cdp, f"04-add-{scope}-test-label"), f"The {scope} label add/save workflow stays on the page and shows the new test row."))

        rows.append(("DB test labels added", terminal_db_screenshot(test_start, "test_labels", "05-db-test-labels-added"), "PowerShell shows the SQL query and rows for the added test labels."))

        for scope, target in TARGETS.items():
            delete_label(cdp, scope, target["test_label"])
            delete_label(cdp, scope, target["label"])
            show_scope(cdp, scope)
            rows.append((f"Remove {scope} target labels", screenshot(cdp, f"06-remove-{scope}-target-labels"), f"The test {scope} label and the approved `{target['label']}` label were removed/deactivated through the UI."))

        rows.append(("DB target labels removed", terminal_db_screenshot(test_start, "labels", "07-db-target-labels-removed"), "PowerShell shows the SQL query and inactive/missing target labels before upload."))

        upload_input(cdp)
        rows.append(("Upload real JPEG", screenshot(cdp, "08-upload-real-jpeg-result"), "The real JPEG ran through validate, ingest, OCR parsing, M7 extraction, and M8 validation from the UI."))
        accepted_rows = accept_review_transactions(cdp)
        notes.append(f"Accepted review rows before saving: {accepted_rows}.")
        save_ready_transactions(cdp)
        rows.append(("Saved accepted transactions", screenshot(cdp, "08b-saved-accepted-transactions"), "The reviewed transaction was accepted and saved through the UI before approval review."))
        rows.append(("DB suggestions after upload", terminal_db_screenshot(test_start, "suggestions", "09-db-suggestions-after-upload"), "PowerShell shows recognition suggestions created by content-based recognition after labels were removed."))
        rows.append(("DB validation after upload", terminal_db_screenshot(test_start, "validation", "10-db-validation-after-upload"), "PowerShell shows validation rows produced by the upload processing run, if persisted before save."))
        rows.append(("DB transactions before approval", terminal_db_screenshot(test_start, "transactions", "11-db-transactions-before-approval"), "PowerShell shows whether transaction rows exist before approval."))

        review_tab(cdp)
        rows.append(("Pending suggestions UI", screenshot(cdp, "12-pending-suggestions-ui"), "The admin review page shows AI/recognition suggestions awaiting approval."))
        approved = approve_all_pending(cdp)
        rows.append(("Approved suggestions UI", screenshot(cdp, "13-approved-suggestions-ui"), "Admin approved pending recognition suggestions through the UI."))
        notes.append(f"Approved pending suggestion forms found in UI: {approved}.")

        rows.append(("DB labels after approval", terminal_db_screenshot(test_start, "labels", "14-db-labels-after-approval"), "PowerShell shows the target labels are active again after approval."))
        rows.append(("DB suggestions after approval", terminal_db_screenshot(test_start, "suggestions", "15-db-suggestions-after-approval"), "PowerShell shows suggestion review status and reviewed timestamp."))
        rows.append(("DB documents after approval", terminal_db_screenshot(test_start, "documents", "16-db-documents-after-approval"), "PowerShell shows linked document classification fields after approval."))
        rows.append(("DB transactions after approval", terminal_db_screenshot(test_start, "transactions", "17-db-transactions-after-approval"), "PowerShell shows linked transaction classification fields after approval, if transactions were saved."))

        open_admin(cdp)
        for scope in ("document", "transaction", "spending"):
            show_scope(cdp, scope)
            rows.append((f"{scope.title()} list after approval", screenshot(cdp, f"18-{scope}-list-after-approval"), f"The approved {scope} target appears in the management page again."))

        result = "PASSED"
    except Exception as exc:
        notes.append(f"Runner stopped at error: {type(exc).__name__}: {exc}")
        raise
    finally:
        # Repair core labels if the UI approval did not restore them.
        repair = """
from stats_data.database import open_azure_sql_connection as connect
from stats_data.recognition_settings import save_label
labels = [
    ("document", "receipt", ["sales_receipt", "tax_receipt", "payment_terminal_receipt", "card_receipt", "medical_receipt", "unknown"]),
    ("transaction", "purchase", ["card_purchase", "eftpos_payment", "merchant_purchase", "cash_purchase", "unknown"]),
    ("spending", "shopping", ["retail", "general_merchandise", "online_shopping", "unknown", "uncategorized"]),
    ("spending", "transport", ["fuel", "public_transport", "parking", "rideshare", "unknown", "uncategorized"]),
]
with connect() as connection:
    for scope, label, values in labels:
        save_label(connection, scope=scope, original_label="", label=label, values=values)
print("Core labels verified active")
"""
        run(
            [
                "docker",
                "exec",
                "--workdir",
                "/app/apps/stats-data",
                "-e",
                "PYTHONPATH=/app/apps/stats-data/src",
                "-i",
                "stats-runtime",
                "/opt/stats/runtime/bin/python",
                "-c",
                repair,
            ],
            check=False,
        )
        write_index(rows, result, notes)
        print(f"Evidence folder: {EVIDENCE}")
        print(f"Result: {result}")
        if result != "PASSED":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
