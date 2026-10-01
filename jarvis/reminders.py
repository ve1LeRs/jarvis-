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
    """Backward-compatible: return (seconds, text) from parse_when()."""
    parsed = parse_when(phrase)
    if not parsed:
        return None
    when, body = parsed
    seconds = max(1, int((when - datetime.now()).total_seconds() + 0.999))
    return seconds, body


def parse_when(phrase: str) -> tuple[datetime, str] | None:
    """Parse relative/absolute reminder phrase into (when, text)."""
    text = (phrase or "").strip().lower().replace("ё", "е")

    absolute = re.match(
        r"^(?:напомни(?:ть)?\s+(?:мне\s+)?)?(?:в|во)\s+(\d{1,2})(?:[:.\s](\d{2}))?\s+(.+)$",
        text,
    )
    if absolute:
        hour = int(absolute.group(1))
        minute = int(absolute.group(2) or "0")
        body = absolute.group(3).strip()
        body = re.sub(r"^\d{2}\s+", "", body).strip() or body
        if not body or hour > 23 or minute > 59:
            return None
        now = datetime.now()
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if when <= now:
            when = when + timedelta(days=1)
        return when, body

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
    return datetime.now() + timedelta(seconds=max(1, seconds)), body


def schedule(seconds: int, text: str) -> str:
    when = datetime.now() + timedelta(seconds=max(1, seconds))
    return schedule_at(when, text)


def schedule_at(when: datetime, text: str) -> str:
    reminder_id = uuid.uuid4().hex[:8]
    seconds = max(1, int((when - datetime.now()).total_seconds() + 0.999))
    timer = threading.Timer(seconds, _fire, args=(reminder_id, text))
    timer.daemon = True
    with _lock:
        _reminders[reminder_id] = Reminder(reminder_id, text, when, timer)
    timer.start()
    delta = when - datetime.now()
    if delta.total_seconds() >= 90:
        return f"Хорошо. Напомню в {when.strftime('%H:%M')}: {text}."
    seconds_i = max(1, int(delta.total_seconds()))
    if seconds_i < 60:
        human = f"{seconds_i} секунд"
    elif seconds_i < 3600:
        human = f"{max(1, seconds_i // 60)} минут"
    else:
        human = f"{max(1, seconds_i // 3600)} час(ов)"
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
