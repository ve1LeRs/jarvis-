"""Cursor IDE helpers."""

from __future__ import annotations

import os
from pathlib import Path

from jarvis.actions import launch


def _find_cursor() -> str | None:
    return launch.which_or_path(
        "cursor",
        [
            r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe",
            r"%LOCALAPPDATA%\Programs\Cursor\Cursor.exe",
            r"%ProgramFiles%\Cursor\Cursor.exe",
            r"%USERPROFILE%\AppData\Local\Programs\cursor\Cursor.exe",
        ],
    )


def open_cursor(path: str | None = None) -> str:
    exe = _find_cursor()
    target = (path or "").strip() or None
    if target:
        expanded = os.path.expandvars(os.path.expanduser(target))
        if not Path(expanded).exists():
            # Friendly aliases
            aliases = {
                "проекты": str(Path.home() / "Projects"),
                "projects": str(Path.home() / "Projects"),
                "документы": str(Path.home() / "Documents"),
                "documents": str(Path.home() / "Documents"),
                "рабочий стол": str(Path.home() / "Desktop"),
                "desktop": str(Path.home() / "Desktop"),
            }
            expanded = aliases.get(target.lower(), expanded)
        if exe:
            launch.run([exe, expanded])
            launch.focus_window(["cursor"])
            return f"Открываю в Cursor: {expanded}."
        if launch.open_uri(f"cursor://file/{expanded}"):
            return f"Открываю в Cursor: {expanded}."
        return f"Cursor не найден, путь был: {expanded}."

    if exe:
        launch.run([exe])
        launch.focus_window(["cursor"])
        return "Открываю Cursor."
    if launch.open_uri("cursor://"):
        return "Открываю Cursor."
    return "Не нашёл Cursor. Установите с cursor.com."


def focus_cursor() -> str:
    if launch.focus_window(["cursor"]):
        return "Переключаюсь на Cursor."
    return open_cursor()


def new_window() -> str:
    exe = _find_cursor()
    if exe:
        launch.run([exe, "-n"])
        return "Открываю новое окно Cursor."
    return open_cursor()


def open_jarvis_repo() -> str:
    # Prefer known clone locations
    candidates = [
        Path.home() / "jarvis-",
        Path.home() / "Projects" / "jarvis-",
        Path.home() / "Documents" / "jarvis-",
        Path.cwd(),
    ]
    for path in candidates:
        if (path / "jarvis").exists() or (path / "JARVIS.py").exists():
            return open_cursor(str(path))
    return open_cursor()
