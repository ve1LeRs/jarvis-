"""Shared Windows/Linux helpers for launching and focusing apps."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

SYSTEM = platform.system()


def run(command: list[str] | str, *, shell: bool = False) -> None:
    kwargs: dict = {"shell": shell}
    if SYSTEM == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(command, **kwargs)


def open_uri(uri: str) -> bool:
    try:
        if SYSTEM == "Windows":
            os.startfile(uri)  # type: ignore[attr-defined]
            return True
        if SYSTEM == "Darwin":
            run(["open", uri])
            return True
        if shutil.which("xdg-open"):
            run(["xdg-open", uri])
            return True
    except OSError:
        return False
    return False


def first_existing(paths: list[str]) -> str | None:
    for raw in paths:
        expanded = os.path.expandvars(os.path.expanduser(raw))
        if "*" in expanded:
            parent = Path(expanded).parent
            pattern = Path(expanded).name
            if parent.exists():
                matches = sorted(parent.glob(pattern), reverse=True)
                if matches:
                    return str(matches[0])
            continue
        if Path(expanded).exists():
            return expanded
    return None


def which_or_path(name: str, candidates: list[str] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if candidates:
        return first_existing(candidates)
    return None


def focus_window(title_substrings: list[str], *, retries: int = 8, delay: float = 0.35) -> bool:
    """Bring a window whose title contains any substring to the foreground (Windows)."""
    if SYSTEM != "Windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    wanted = [s.lower() for s in title_substrings if s]

    for _ in range(max(1, retries)):
        found_hwnd = wintypes.HWND()

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):  # type: ignore[misc]
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.lower()
            if any(w in title for w in wanted):
                found_hwnd.value = hwnd
                return False
            return True

        user32.EnumWindows(_enum, 0)
        if found_hwnd.value:
            user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(found_hwnd)
            return True
        time.sleep(delay)
    return False


def send_hotkey(*keys: str) -> bool:
    """Send a hotkey combo like ('ctrl', 'shift', 'm') on Windows."""
    if SYSTEM != "Windows":
        return False
    try:
        import ctypes
    except Exception:
        return False

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    KEYEVENTF_KEYUP = 0x0002
    vk = {
        "ctrl": 0x11,
        "control": 0x11,
        "shift": 0x10,
        "alt": 0x12,
        "win": 0x5B,
        "enter": 0x0D,
        "tab": 0x09,
        "esc": 0x1B,
        "f5": 0x74,
        "t": 0x54,
        "w": 0x57,
        "n": 0x4E,
        "l": 0x4C,
        "r": 0x52,
        "m": 0x4D,
        "d": 0x44,
        "k": 0x4B,
        "o": 0x4F,
        "s": 0x53,
        "p": 0x50,
    }
    codes: list[int] = []
    for key in keys:
        code = vk.get(key.lower())
        if code is None and len(key) == 1:
            code = ord(key.upper())
        if code is None:
            return False
        codes.append(code)

    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)
    return True


def steam_run(app_id: int | str) -> bool:
    return open_uri(f"steam://rungameid/{app_id}")


def find_steam_exe() -> str | None:
    return which_or_path(
        "steam",
        [
            r"%ProgramFiles(x86)%\Steam\steam.exe",
            r"%ProgramFiles%\Steam\steam.exe",
            r"%LOCALAPPDATA%\Programs\Steam\steam.exe",
        ],
    )
