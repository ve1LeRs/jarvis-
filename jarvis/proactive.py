"""Background proactive nudges: morning brief, game time, todo reminders."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable

from jarvis import context
from jarvis import memory
from jarvis.actions import calendar as cal

Speaker = Callable[[str], None]

_lock = threading.RLock()
_state = {
    "morning_done_day": "",
    "last_todo_nudge": 0.0,
    "last_game_nudge": 0.0,
    "game_started_at": 0.0,
    "enabled": True,
}
_thread: threading.Thread | None = None
_stop = threading.Event()
_speaker: Speaker | None = None


def set_speaker(fn: Speaker) -> None:
    global _speaker
    _speaker = fn


def enable(value: bool = True) -> str:
    with _lock:
        _state["enabled"] = bool(value)
    return "Проактивность включена." if value else "Проактивность выключена."


def is_enabled() -> bool:
    with _lock:
        return bool(_state["enabled"])


def note_game_started() -> None:
    with _lock:
        _state["game_started_at"] = time.time()


def note_game_ended() -> None:
    with _lock:
        _state["game_started_at"] = 0.0


def build_morning_brief() -> str:
    parts = [memory.today_brief()]
    cal_text = cal.today_events_text()
    if "не подключён" not in cal_text.lower() and "ничего нет" not in cal_text.lower():
        parts.append(cal_text)
    upcoming = cal.upcoming_text(hours=12)
    if "нет" not in upcoming.lower():
        parts.append(upcoming)
    return " ".join(parts)


def _tick() -> None:
    if not is_enabled() or _speaker is None:
        return
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # Morning brief 07:00–10:59 once per day
    with _lock:
        morning_done = _state["morning_done_day"]
    if 7 <= now.hour < 11 and morning_done != today:
        _speaker("Доброе утро. " + build_morning_brief())
        with _lock:
            _state["morning_done_day"] = today

    # Todo nudge every 3 hours if open todos exist
    open_todos = []
    try:
        raw = memory._read_json(memory.TODOS_FILE, [])  # noqa: SLF001
        if isinstance(raw, list):
            open_todos = [t for t in raw if not t.get("done")]
    except Exception:
        open_todos = []
    with _lock:
        last_todo = float(_state["last_todo_nudge"])
    if open_todos and time.time() - last_todo > 3 * 3600 and now.hour >= 10:
        names = "; ".join(str(t.get("text", "")) for t in open_todos[:3])
        _speaker(f"Напоминание по делам: {names}.")
        with _lock:
            _state["last_todo_nudge"] = time.time()

    # Game duration nudge
    ctx = context.get()
    with _lock:
        started = float(_state["game_started_at"])
        last_game = float(_state["last_game_nudge"])
    if ctx.mode == "game" and started and time.time() - started > 90 * 60:
        if time.time() - last_game > 45 * 60:
            mins = int((time.time() - started) / 60)
            _speaker(f"Вы уже {mins} минут в игре. Нужен перерыв или выход из игрового режима?")
            with _lock:
                _state["last_game_nudge"] = time.time()
    elif ctx.mode != "game" and started:
        note_game_ended()


def _loop() -> None:
    # stagger first tick
    _stop.wait(20)
    while not _stop.is_set():
        try:
            _tick()
        except Exception:
            pass
        _stop.wait(60)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="jarvis-proactive")
    _thread.start()


def stop() -> None:
    _stop.set()


def status_text() -> str:
    on = "вкл" if is_enabled() else "выкл"
    return f"Проактивность: {on}. Утренний брифинг, дела и контроль времени в игре."
