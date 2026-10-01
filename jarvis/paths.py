"""Autodetect and cache paths to Chrome, Steam, Spotify, Discord, etc."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any

from jarvis import memory
from jarvis.actions import launch

PATHS_KEY = "app_paths"
SYSTEM = platform.system()


_CANDIDATES: dict[str, list[str]] = {
    "chrome": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "spotify": [
        r"%APPDATA%\Spotify\Spotify.exe",
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
        "/usr/bin/spotify",
        "/Applications/Spotify.app/Contents/MacOS/Spotify",
    ],
    "steam": [
        r"%ProgramFiles(x86)%\Steam\steam.exe",
        r"%ProgramFiles%\Steam\steam.exe",
        r"%LocalAppData%\Steam\steam.exe",
        "~/.steam/steam/steam.sh",
        "/usr/bin/steam",
        "/Applications/Steam.app/Contents/MacOS/steam_osx",
    ],
    "discord": [
        r"%LOCALAPPDATA%\Discord\Update.exe",
        r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
        "/usr/bin/discord",
        "/Applications/Discord.app/Contents/MacOS/Discord",
    ],
    "cursor": [
        r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe",
        r"%LOCALAPPDATA%\Programs\Cursor\Cursor.exe",
        "/usr/bin/cursor",
        "/Applications/Cursor.app/Contents/MacOS/Cursor",
    ],
    "word": [
        r"%ProgramFiles%\Microsoft Office\root\Office16\WINWORD.EXE",
        r"%ProgramFiles(x86)%\Microsoft Office\root\Office16\WINWORD.EXE",
        r"%ProgramFiles%\Microsoft Office\Office16\WINWORD.EXE",
        "/usr/bin/libreoffice",
    ],
}


def detect_all() -> dict[str, str]:
    found: dict[str, str] = {}
    for name, candidates in _CANDIDATES.items():
        # which() first for unix-friendly names
        which_name = {
            "chrome": "google-chrome",
            "spotify": "spotify",
            "steam": "steam",
            "discord": "discord",
            "cursor": "cursor",
            "word": "winword",
        }.get(name, name)
        path = shutil.which(which_name) or launch.first_existing(candidates)
        if path:
            found[name] = path
    # Windows registry hints (best-effort)
    if SYSTEM == "Windows":
        found.update(_detect_windows_registry())
    memory.update_settings(**{PATHS_KEY: found})
    return found


def _detect_windows_registry() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        import winreg  # type: ignore
    except ImportError:
        return out

    probes = [
        ("chrome", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        ("steam", winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam", "SteamExe"),
    ]
    for app, hive, key_path, *rest in probes:
        value_name = rest[0] if rest else None
        try:
            with winreg.OpenKey(hive, key_path) as key:
                if value_name:
                    val, _ = winreg.QueryValueEx(key, value_name)
                else:
                    val, _ = winreg.QueryValueEx(key, None)
                if val and Path(str(val)).exists():
                    out[app] = str(val)
        except OSError:
            continue
    return out


def get_path(app: str) -> str | None:
    settings = memory.get_settings()
    cached = settings.get(PATHS_KEY) or {}
    if isinstance(cached, dict) and cached.get(app):
        path = str(cached[app])
        if Path(os.path.expandvars(path)).exists() or shutil.which(path):
            return path
    found = detect_all()
    return found.get(app)


def status_text() -> str:
    paths = memory.get_settings().get(PATHS_KEY) or {}
    if not isinstance(paths, dict) or not paths:
        paths = detect_all()
    if not paths:
        return "Программы не найдены. Установите Chrome, Steam, Spotify или Discord."
    parts = [f"{k}: найден" for k in sorted(paths)]
    return "Профиль ПК: " + "; ".join(parts) + "."


def ensure_detected() -> dict[str, Any]:
    cached = memory.get_settings().get(PATHS_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return detect_all()
