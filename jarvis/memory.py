"""Persistent memory: settings, notes, command history."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".jarvis"
SETTINGS_FILE = DATA_DIR / "settings.json"
NOTES_FILE = DATA_DIR / "notes.json"
HISTORY_FILE = DATA_DIR / "history.json"
TODOS_FILE = DATA_DIR / "todos.json"

_lock = threading.RLock()

_DEFAULT_SETTINGS: dict[str, Any] = {
    "muted": False,
    "quiet_mode": False,
    "voice": None,
    "last_command": "",
}


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    _ensure_dir()
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    _ensure_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_settings() -> dict[str, Any]:
    with _lock:
        data = _read_json(SETTINGS_FILE, dict(_DEFAULT_SETTINGS))
        merged = dict(_DEFAULT_SETTINGS)
        merged.update(data if isinstance(data, dict) else {})
        return merged


def update_settings(**kwargs: Any) -> dict[str, Any]:
    with _lock:
        settings = get_settings()
        settings.update(kwargs)
        _write_json(SETTINGS_FILE, settings)
        return settings


def is_muted() -> bool:
    return bool(get_settings().get("muted"))


def set_muted(value: bool) -> None:
    update_settings(muted=value)


def add_note(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Пустая заметка."
    with _lock:
        notes = _read_json(NOTES_FILE, [])
        if not isinstance(notes, list):
            notes = []
        notes.append(
            {
                "text": text,
                "created": datetime.now().isoformat(timespec="seconds"),
            }
        )
        _write_json(NOTES_FILE, notes)
    return f"Записал заметку: {text}"


def list_notes(limit: int = 5) -> str:
    with _lock:
        notes = _read_json(NOTES_FILE, [])
    if not isinstance(notes, list) or not notes:
        return "Заметок пока нет."
    recent = notes[-limit:]
    lines = [f"{i}. {n.get('text', '')}" for i, n in enumerate(recent, 1)]
    return "Последние заметки: " + "; ".join(lines)


def clear_notes() -> str:
    with _lock:
        _write_json(NOTES_FILE, [])
    return "Все заметки удалены."


def remember_command(command: str) -> None:
    command = (command or "").strip()
    if not command:
        return
    with _lock:
        update_settings(last_command=command)
        history = _read_json(HISTORY_FILE, [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "command": command,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        history = history[-100:]
        _write_json(HISTORY_FILE, history)


def last_command() -> str:
    return str(get_settings().get("last_command") or "")


def recent_history(limit: int = 5) -> list[str]:
    with _lock:
        history = _read_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        return []
    return [str(item.get("command", "")) for item in history[-limit:] if item.get("command")]


def add_todo(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Пустое дело."
    with _lock:
        todos = _read_json(TODOS_FILE, [])
        if not isinstance(todos, list):
            todos = []
        todos.append(
            {
                "text": text,
                "done": False,
                "created": datetime.now().isoformat(timespec="seconds"),
            }
        )
        _write_json(TODOS_FILE, todos)
    return f"Добавил в дела: {text}."


def list_todos() -> str:
    with _lock:
        todos = _read_json(TODOS_FILE, [])
    if not isinstance(todos, list):
        return "Список дел пуст."
    open_items = [t for t in todos if not t.get("done")]
    if not open_items:
        return "На сегодня открытых дел нет."
    lines = [f"{i}. {t.get('text', '')}" for i, t in enumerate(open_items[:10], 1)]
    return "Дела: " + "; ".join(lines)


def complete_todo(query: str) -> str:
    needle = (query or "").strip().lower()
    with _lock:
        todos = _read_json(TODOS_FILE, [])
        if not isinstance(todos, list) or not todos:
            return "Список дел пуст."
        for item in todos:
            if item.get("done"):
                continue
            text = str(item.get("text", ""))
            if not needle or needle in text.lower():
                item["done"] = True
                _write_json(TODOS_FILE, todos)
                return f"Отметил выполненным: {text}."
    return "Не нашёл такое дело."


def today_brief() -> str:
    """Short daily briefing from todos + reminders-like notes."""
    with _lock:
        todos = _read_json(TODOS_FILE, [])
        notes = _read_json(NOTES_FILE, [])
    open_todos = [t.get("text", "") for t in todos if isinstance(todos, list) and not t.get("done")]
    recent_notes = []
    if isinstance(notes, list) and notes:
        recent_notes = [n.get("text", "") for n in notes[-3:]]
    weekday = (
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )[datetime.now().weekday()]
    parts = [f"Сегодня {weekday}, {datetime.now().strftime('%d.%m')}."]
    if open_todos:
        parts.append("Дела: " + "; ".join(open_todos[:5]) + ".")
    else:
        parts.append("Открытых дел нет.")
    if recent_notes:
        parts.append("Недавние заметки: " + "; ".join(recent_notes) + ".")
    return " ".join(parts)
