"""Simple in-process reminders (survive until process exit)."""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

SpeakFn = Callable[[str], None]


@dataclass
class Reminder:
    id: str
    text: str
    when: datetime
    timer: threading.Timer


_reminders: dict[str, Reminder] = {}
_lock = threading.Lock()
_speak: SpeakFn | None = None


def set_speaker(fn: SpeakFn) -> None:
    global _speak
    _speak = fn


def _fire(reminder_id: str, text: str) -> None:
    with _lock:
        _reminders.pop(reminder_id, None)
    msg = f"Напоминание, сэр: {text}"
    if _speak:
        _speak(msg)
    else:
        print(f"JARVIS: {msg}")


def parse_delay(phrase: str) -> tuple[int, str] | None:
    """Parse 'через 5 минут купить молоко' → (seconds, text)."""
    text = (phrase or "").strip().lower().replace("ё", "е")
    match = re.match(
        r"^через\s+(\d+)\s*(секунд[уы]?|сек|минут[уы]?|мин|час(?:а|ов)?|ч)?\s*(?:напомни(?:ть)?\s+)?(.+)$",
        text,
    )
    if not match:
        match = re.match(
            r"^напомни(?:ть)?\s+(?:мне\s+)?через\s+(\d+)\s*(секунд[уы]?|сек|минут[уы]?|мин|час(?:а|ов)?|ч)?\s+(.+)$",
            text,
        )
    if not match:
        return None
    amount = int(match.group(1))
    unit = (match.group(2) or "мин").lower()
    body = match.group(3).strip()
    if not body:
        return None
    if unit.startswith("сек") or unit == "сек":
        seconds = amount
    elif unit.startswith("час") or unit == "ч":
        seconds = amount * 3600
    else:
        seconds = amount * 60
    return max(1, seconds), body


def schedule(seconds: int, text: str) -> str:
    reminder_id = uuid.uuid4().hex[:8]
    when = datetime.now() + timedelta(seconds=seconds)
    timer = threading.Timer(seconds, _fire, args=(reminder_id, text))
    timer.daemon = True
    with _lock:
        _reminders[reminder_id] = Reminder(reminder_id, text, when, timer)
    timer.start()
    if seconds < 60:
        human = f"{seconds} секунд"
    elif seconds < 3600:
        human = f"{max(1, seconds // 60)} минут"
    else:
        human = f"{max(1, seconds // 3600)} час(ов)"
    return f"Хорошо. Напомню через {human}: {text}."


def list_reminders() -> str:
    with _lock:
        items = list(_reminders.values())
    if not items:
        return "Активных напоминаний нет."
    parts = []
    for item in items:
        parts.append(f"{item.text} ({item.when.strftime('%H:%M')})")
    return "Напоминания: " + "; ".join(parts)


def clear_reminders() -> str:
    with _lock:
        for item in _reminders.values():
            item.timer.cancel()
        _reminders.clear()
    return "Все напоминания отменены."
