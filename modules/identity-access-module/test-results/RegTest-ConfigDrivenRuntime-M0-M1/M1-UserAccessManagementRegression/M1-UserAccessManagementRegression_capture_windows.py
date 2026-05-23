"""M1 focused Windows Edge and terminal regression evidence capture."""

# M1 - User Access Management Start
# Captures visible Edge and terminal proof for the config-driven M1 regression checks.
from __future__ import annotations

import ctypes
import subprocess
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path
from typing import Callable

from PIL import ImageGrab


OUTPUT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = Path(__file__).resolve().parents[3]
CAPTURE_DATE = "2026-05-23"
EDGE_EXECUTABLE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_SIZE = (1120, 820)
EDGE_POSITION = (30, 30)
TERMINAL_SIZE = (1500, 900)
TERMINAL_POSITION = (20, 20)
SW_RESTORE = 9
SW_MINIMIZE = 6

user32 = ctypes.windll.user32


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _visible_windows() -> list[tuple[int, str, str]]:
    windows: list[tuple[int, str, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_windows(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            title = _window_text(hwnd)
            if title:
                windows.append((hwnd, title, _window_class(hwnd)))
        return True

    user32.EnumWindows(enum_windows, 0)
    return windows


def _wait_for_window(predicate: Callable[[int, str, str], bool], before: set[int]) -> int:
    for _ in range(40):
        for hwnd, title, class_name in _visible_windows():
            if hwnd not in before and predicate(hwnd, title, class_name):
                return hwnd
        time.sleep(0.5)
    raise RuntimeError("Evidence window did not appear")


def _place_and_capture(hwnd: int, position: tuple[int, int], size: tuple[int, int], output: Path) -> None:
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.MoveWindow(hwnd, position[0], position[1], size[0], size[1], True)
    user32.SetForegroundWindow(hwnd)
    time.sleep(2)
    ImageGrab.grab(bbox=_window_rect(hwnd)).save(output)
    print(f"captured {output.name}")


def _minimize_evidence_terminals() -> None:
    for hwnd, title, class_name in _visible_windows():
        if class_name == "CASCADIA_HOSTING_WINDOW_CLASS" and "M1 Config Runtime Regression Evidence" in title:
            user32.ShowWindow(hwnd, SW_MINIMIZE)


def capture_edge(url: str, output_name: str) -> None:
    _minimize_evidence_terminals()
    before = {hwnd for hwnd, _, _ in _visible_windows()}
    subprocess.Popen(
        [
            EDGE_EXECUTABLE,
            "--new-window",
            url,
            f"--window-position={EDGE_POSITION[0]},{EDGE_POSITION[1]}",
            f"--window-size={EDGE_SIZE[0]},{EDGE_SIZE[1]}",
        ]
    )
    hwnd = _wait_for_window(
        lambda _hwnd, title, class_name: (
            class_name == "Chrome_WidgetWin_1"
            and "Welcome to Microsoft Edge" not in title
        ),
        before,
    )
    _place_and_capture(hwnd, EDGE_POSITION, EDGE_SIZE, OUTPUT_DIR / output_name)


def capture_terminal() -> None:
    before = {hwnd for hwnd, _, _ in _visible_windows()}
    command = (
        "$host.UI.RawUI.WindowTitle='M1 Config Runtime Regression Evidence'; "
        f"Set-Location '{SERVICE_ROOT}'; "
        "Clear-Host; "
        "python test-results\\RegTest-ConfigDrivenRuntime-M0-M1\\M1-UserAccessManagementRegression\\M1-UserAccessManagementRegression_terminal_check.py"
    )
    subprocess.Popen(
        ["powershell.exe", "-NoExit", "-Command", command],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    hwnd = _wait_for_window(
        lambda _hwnd, title, _class_name: "M1 Config Runtime Regression Evidence" in title,
        before,
    )
    time.sleep(12)
    _place_and_capture(
        hwnd,
        TERMINAL_POSITION,
        TERMINAL_SIZE,
        OUTPUT_DIR / f"M1-UserAccessManagementRegression-windows-terminal-test-{CAPTURE_DATE}.png",
    )


def _wait_for_url(url: str) -> None:
    for _ in range(40):
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Local evidence target did not become ready: {url}")


def main() -> None:
    _wait_for_url("http://127.0.0.1:8013/health")
    _wait_for_url("http://127.0.0.1:5013/Login")
    capture_edge(
        "http://127.0.0.1:5013/Login",
        f"M1-UserAccessManagementRegression-windows-browser-dotnet-login-{CAPTURE_DATE}.png",
    )
    capture_edge(
        "http://127.0.0.1:8013/docs",
        f"M1-UserAccessManagementRegression-windows-browser-api-docs-{CAPTURE_DATE}.png",
    )
    capture_edge(
        "http://127.0.0.1:8013/api/v1/auth/me",
        f"M1-UserAccessManagementRegression-windows-browser-auth-me-unauthenticated-{CAPTURE_DATE}.png",
    )
    capture_terminal()


if __name__ == "__main__":
    main()
# M1 End
