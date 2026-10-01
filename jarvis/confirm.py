"""Confirmation gate for dangerous actions."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class Pending:
    action: str
    label: str
    runner: Callable[[], tuple[bool, str, str]]
    created: float


_lock = threading.Lock()
_pending: Pending | None = None
_TTL_SECONDS = 45.0


def clear() -> None:
    global _pending
    with _lock:
        _pending = None


def ask(action: str, label: str, runner: Callable[[], tuple[bool, str, str]]) -> tuple[bool, str, str]:
    """Register pending action. Returns (ok, spoken, detail)."""
    global _pending
    with _lock:
        _pending = Pending(action=action, label=label, runner=runner, created=time.time())
    return (
        True,
        f"Подтвердите: {label}. Скажите «подтверди» или «отмена».",
        "__CONFIRM__",
    )


def has_pending() -> bool:
    with _lock:
        if _pending is None:
            return False
        if time.time() - _pending.created > _TTL_SECONDS:
            return False
        return True


def confirm() -> tuple[bool, str, str]:
    global _pending
    with _lock:
        item = _pending
        _pending = None
    if item is None or time.time() - item.created > _TTL_SECONDS:
        return False, "Нечего подтверждать.", ""
    return item.runner()


def cancel_pending() -> tuple[bool, str, str]:
    had = has_pending()
    clear()
    if had:
        return True, "Отменил опасное действие.", ""
    return False, "", ""
