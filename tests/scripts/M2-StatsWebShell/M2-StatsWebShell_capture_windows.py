"""M2 - Stats Web Shell Start
Captures visible Windows Edge evidence for the M2 dashboard-first shell flow.
M2 End"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path
from typing import Callable

from PIL import ImageGrab


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests/scripts" / "common"))
from test_config import configured_path, configured_url, load_settings

SETTINGS = load_settings(__file__)
OUTPUT_DIR = configured_path(__file__, "evidenceFolders", "M2StatsWebShell")
IDENTITY_ROOT = configured_path(__file__, "moduleFolders", "IdentityAccess")
WEB_ROOT = configured_path(__file__, "moduleFolders", "StatsWeb")
CAPTURE_DATE = "2026-05-24"
EDGE_SIZE = (1240, 880)
EDGE_POSITION = (25, 25)
SW_RESTORE = 9

ADMIN_EMAIL = "m2.evidence.admin.20260524@example.com"
ADMIN_PASSWORD = "M2EvidenceTemp123"

user32 = ctypes.windll.user32


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
    for _ in range(80):
        for hwnd, title, class_name in visible_windows():
            if hwnd not in before and predicate(hwnd, title, class_name):
                return hwnd
        time.sleep(0.3)
    raise RuntimeError("Evidence Edge window did not appear")


def wait_for_url(url: str) -> None:
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Local evidence target did not become ready: {url}")


def capture(hwnd: int, name: str) -> None:
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.MoveWindow(hwnd, EDGE_POSITION[0], EDGE_POSITION[1], EDGE_SIZE[0], EDGE_SIZE[1], True)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.0)
    output = OUTPUT_DIR / name
    ImageGrab.grab(bbox=window_rect(hwnd)).save(output)
    print(f"captured {output.name}")


def start_processes() -> list[subprocess.Popen[bytes]]:
    db_path = (OUTPUT_DIR / "M2-StatsWebShell-identity-evidence.db").as_posix()
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["DEFAULT_ADMIN_EMAIL"] = ADMIN_EMAIL
    env["DEFAULT_ADMIN_PASSWORD"] = ADMIN_PASSWORD
    env["API_HOST"] = SETTINGS["runtime"]["identityHost"]
    env["API_PORT"] = SETTINGS["runtime"]["identityPort"]

    subprocess.run(
        [sys.executable, "-m", "app.scripts.create_admin"],
        cwd=IDENTITY_ROOT,
        env=env,
        check=True,
    )

    return [
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
            cwd=IDENTITY_ROOT,
            env=env,
        ),
        subprocess.Popen(
            ["dotnet", "run", "--urls", SETTINGS["runtime"]["statsWebBaseUrl"]],
            cwd=WEB_ROOT,
            env=env,
        ),
    ]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for marker in OUTPUT_DIR.glob("*.ready"):
        marker.unlink()
    for marker in OUTPUT_DIR.glob("*.done"):
        marker.unlink()
    evidence_db = OUTPUT_DIR / "M2-StatsWebShell-identity-evidence.db"
    if evidence_db.exists():
        evidence_db.unlink()

    processes = start_processes()
    node_process: subprocess.Popen[bytes] | None = None
    try:
        wait_for_url(configured_url(__file__, "identityBaseUrl", "health"))
        wait_for_url(configured_url(__file__, "statsWebBaseUrl", "Login"))

        before = {hwnd for hwnd, _, _ in visible_windows()}
        node_env = os.environ.copy()
        bundled_node_modules = (
            Path.home()
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "node"
            / "node_modules"
        )
        if bundled_node_modules.exists():
            pnpm_node_modules = bundled_node_modules / ".pnpm" / "node_modules"
            node_paths = [str(bundled_node_modules)]
            if pnpm_node_modules.exists():
                node_paths.append(str(pnpm_node_modules))
            node_env["NODE_PATH"] = os.pathsep.join(node_paths)

        node_process = subprocess.Popen(
            ["node", str(SCRIPT_DIR / "M2-StatsWebShell_playwright.js")],
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
            "login": f"M2-StatsWebShell-windows-browser-login-{CAPTURE_DATE}.png",
            "password-setup": f"M2-StatsWebShell-windows-browser-password-setup-{CAPTURE_DATE}.png",
            "dashboard-home": f"M2-StatsWebShell-windows-browser-dashboard-home-{CAPTURE_DATE}.png",
            "upload-documents": f"M2-StatsWebShell-windows-browser-upload-documents-{CAPTURE_DATE}.png",
            "email-setup": f"M2-StatsWebShell-windows-browser-email-setup-{CAPTURE_DATE}.png",
            "documents": f"M2-StatsWebShell-windows-browser-documents-{CAPTURE_DATE}.png",
            "reports": f"M2-StatsWebShell-windows-browser-reports-{CAPTURE_DATE}.png",
            "admin-users": f"M2-StatsWebShell-windows-browser-admin-users-{CAPTURE_DATE}.png",
            "standard-user-blocked": f"M2-StatsWebShell-windows-browser-standard-user-blocked-{CAPTURE_DATE}.png",
        }
        for marker, output_name in checkpoints.items():
            ready_path = OUTPUT_DIR / f"{marker}.ready"
            done_path = OUTPUT_DIR / f"{marker}.done"
            for _ in range(180):
                if ready_path.exists():
                    capture(hwnd, output_name)
                    done_path.write_text("captured", encoding="utf-8")
                    break
                if node_process.poll() is not None:
                    raise RuntimeError(f"Playwright flow exited before checkpoint: {marker}")
                time.sleep(0.25)
            else:
                raise RuntimeError(f"Timed out waiting for checkpoint: {marker}")

        node_exit = node_process.wait(timeout=80)
        if node_exit != 0:
            raise RuntimeError(f"Playwright evidence flow failed with exit code {node_exit}")
        print("M2 Stats Web Shell visible Edge evidence")
        print("Routes: /Login, /, /Upload, /EmailSetup, /Documents, /Reports, /Users")
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
        if evidence_db.exists():
            evidence_db.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
