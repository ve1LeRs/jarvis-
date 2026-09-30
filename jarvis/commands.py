"""Natural-language command router (Russian + English)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable

from jarvis import config
from jarvis.actions import system as act


@dataclass
class Result:
    ok: bool
    spoken: str
    detail: str = ""


Handler = Callable[[str], Result]


def _ok(spoken: str, detail: str = "") -> Result:
    return Result(True, spoken, detail or spoken)


def _fail(spoken: str | None = None) -> Result:
    return Result(False, spoken or random.choice(config.NOT_UNDERSTOOD))


# Patterns are checked in order. Group 1 is usually the payload.
_RULES: list[tuple[re.Pattern[str], str]] = [
    # Search
    (re.compile(r"^(?:найди|найти|поищи|поиск|загугли|google)\s+(?:информацию\s+о(?:б)?\s+|про\s+|о(?:б)?\s+)?(.+)$"), "search"),
    (re.compile(r"^(?:что\s+такое|кто\s+такой|кто\s+такая)\s+(.+)$"), "search"),
    (re.compile(r"^(?:search|look\s+up|find(?:\s+info(?:rmation)?)?(?:\s+about)?)\s+(.+)$"), "search"),
    # Open explorer
    (re.compile(r"^(?:открой|открыть|запусти|запустить)\s+(?:проводник|explorer|файловый\s+менеджер|файлы)$"), "explorer"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?загрузки$"), "downloads"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?(?:рабочий\s+стол|desktop)$"), "desktop"),
    # Open browser / chrome
    (re.compile(r"^(?:открой|открыть|запусти)\s+(?:хром|chrome|браузер)(?:\s+(.+))?$"), "chrome"),
    # Open named app / site
    (re.compile(r"^(?:открой|открыть|запусти|запустить)\s+(.+)$"), "open"),
    # Time / date
    (re.compile(r"^(?:который\s+час|сколько\s+времени|время|what\s+time)$"), "time"),
    (re.compile(r"^(?:какое\s+сегодня\s+число|какая\s+дата|дата|what\s+date)$"), "date"),
    # System
    (re.compile(r"^(?:выключи(?:\s+компьютер)?|shutdown|выключение)$"), "shutdown"),
    (re.compile(r"^(?:отмена|отмени(?:\s+выключение)?|cancel)$"), "cancel_shutdown"),
    (re.compile(r"^(?:заблокируй|блокировка|lock)$"), "lock"),
    # Greetings / help
    (re.compile(r"^(?:привет|здравствуй|hello|hi)$"), "hello"),
    (re.compile(r"^(?:спасибо|благодарю|thanks)$"), "thanks"),
    (re.compile(r"^(?:помощь|help|что\s+ты\s+умеешь|команды)$"), "help"),
    (re.compile(r"^(?:пока|до\s+свидания|выключись|стоп|exit|quit)$"), "bye"),
]


def parse_and_run(command: str) -> Result:
    text = (command or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^\w\s\-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return _fail()

    for pattern, action in _RULES:
        match = pattern.match(text)
        if not match:
            continue
        payload = (match.group(1) if match.lastindex else "") or ""
        payload = payload.strip()
        return _dispatch(action, payload, text)

    # Soft fallback: if it looks like a search intent, search it.
    if any(w in text for w in ("найди", "поиск", "информац", "что такое")):
        cleaned = re.sub(
            r"^(?:джарвис|jarvis)?\s*(?:найди|поищи|поиск)?\s*(?:информацию\s+о(?:б)?)?\s*",
            "",
            text,
        ).strip()
        if cleaned:
            return _dispatch("search", cleaned, text)

    return _fail()


def _dispatch(action: str, payload: str, raw: str) -> Result:
    if action == "search":
        msg = act.search_web(payload)
        return _ok(f"{random.choice(config.ACKNOWLEDGMENTS)} Ищу информацию о {payload}.", msg)

    if action == "explorer":
        return _ok(f"{random.choice(config.ACKNOWLEDGMENTS)} Открываю проводник.", act.open_explorer())

    if action == "downloads":
        return _ok("Открываю папку загрузок.", act.open_downloads())

    if action == "desktop":
        return _ok("Открываю рабочий стол.", act.open_desktop())

    if action == "chrome":
        if payload:
            # "открой хром ютуб" etc.
            if payload in {"youtube", "ютуб", "ютубе"}:
                return _ok("Открываю YouTube.", act.open_url("https://www.youtube.com"))
            return _ok("Открываю Chrome с поиском.", act.search_web(payload))
        return _ok(random.choice(config.ACKNOWLEDGMENTS), act.open_chrome())

    if action == "open":
        # Prefer treating unknown "open X" as app/site; if multi-word research-like, search.
        known_sites = {
            "youtube",
            "ютуб",
            "ютубе",
            "почта",
            "gmail",
            "переводчик",
            "погода",
            "хром",
            "chrome",
            "браузер",
        }
        first = payload.split()[0] if payload else ""
        if payload in known_sites or first in known_sites:
            return _ok(random.choice(config.ACKNOWLEDGMENTS), act.open_app(payload if payload in known_sites else first))
        # "открой википедию про X" -> search
        wiki = re.match(r"^(?:википедию|wikipedia)\s+(?:про\s+|о(?:б)?\s+)?(.+)$", payload)
        if wiki:
            q = wiki.group(1)
            return _ok(f"Ищу {q} в Википедии.", act.search_web(f"site:wikipedia.org {q}"))
        detail = act.open_app(payload)
        return _ok(f"{random.choice(config.ACKNOWLEDGMENTS)} {detail}", detail)

    if action == "time":
        return _ok(act.tell_time())

    if action == "date":
        return _ok(act.tell_date())

    if action == "shutdown":
        return _ok(act.shutdown_pc())

    if action == "cancel_shutdown":
        return _ok(act.cancel_shutdown())

    if action == "lock":
        return _ok(act.lock_pc())

    if action == "hello":
        return _ok(random.choice(config.GREETINGS))

    if action == "thanks":
        return _ok("Всегда рад помочь, сэр.")

    if action == "help":
        help_text = (
            "Я могу искать информацию в Chrome, открывать проводник, браузер, "
            "YouTube, загрузки, говорить время и дату, блокировать компьютер. "
            "Скажите, например: джарвис, найди информацию о сосновом брусе."
        )
        return _ok(help_text)

    if action == "bye":
        return Result(True, "До связи, сэр.", detail="__EXIT__")

    return _fail(f"Неизвестное действие для: {raw}")
