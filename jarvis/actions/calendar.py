"""Calendar via public ICS feeds (Google/Outlook export links)."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from jarvis import memory

CALENDAR_FILE = memory.DATA_DIR / "calendar.json"


def _load() -> dict:
    data = memory._read_json(CALENDAR_FILE, {"feeds": [], "cache": []})  # noqa: SLF001
    if not isinstance(data, dict):
        return {"feeds": [], "cache": []}
    data.setdefault("feeds", [])
    data.setdefault("cache", [])
    return data


def _save(data: dict) -> None:
    memory._write_json(CALENDAR_FILE, data)  # noqa: SLF001


def add_feed(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return (
            "Нужна ссылка на ICS. В Google Calendar: Настройки → календарь → "
            "«Секретный адрес в формате iCal». В Outlook: Поделиться → ICS."
        )
    data = _load()
    feeds = list(data.get("feeds") or [])
    if url not in feeds:
        feeds.append(url)
        data["feeds"] = feeds
        _save(data)
    refresh_feeds()
    return f"Календарь добавлен. Сейчас в лентах: {len(feeds)}."


def list_feeds() -> str:
    feeds = _load().get("feeds") or []
    if not feeds:
        return "Календарей нет. Скажите: добавь календарь и ссылку ICS."
    return "Календари: " + "; ".join(feeds[:5])


def clear_feeds() -> str:
    _save({"feeds": [], "cache": []})
    return "Календари очищены."


def _unfold(ics: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", ics)


def _parse_ics_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    value = value.split(";")[-1] if ":" in value and value.upper().startswith("TZID") else value
    # VALUE=DATE:20260101 or 20260101T180000Z
    value = value.split(":")[-1] if ":" in value and not value[:8].isdigit() else value
    value = value.replace("Z", "")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(value[: len(datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    # try fixed lengths
    try:
        if len(value) >= 15:
            return datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
        if len(value) >= 8:
            return datetime.strptime(value[:8], "%Y%m%d")
    except ValueError:
        return None
    return None


def parse_ics(text: str) -> list[dict]:
    """Parse VEVENT blocks into {summary, start, end} dicts."""
    text = _unfold(text or "")
    events: list[dict] = []
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.S | re.I)
    for block in blocks:
        summary = ""
        start = None
        end = None
        for line in block.splitlines():
            line = line.strip()
            upper = line.upper()
            if upper.startswith("SUMMARY"):
                summary = line.split(":", 1)[-1].strip()
            elif upper.startswith("DTSTART"):
                start = _parse_ics_datetime(line.split(":", 1)[-1].strip())
            elif upper.startswith("DTEND"):
                end = _parse_ics_datetime(line.split(":", 1)[-1].strip())
        if summary and start:
            events.append(
                {
                    "summary": summary,
                    "start": start.isoformat(timespec="seconds"),
                    "end": end.isoformat(timespec="seconds") if end else "",
                }
            )
    return events


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def refresh_feeds() -> str:
    data = _load()
    feeds = list(data.get("feeds") or [])
    if not feeds:
        return "Нет календарных лент."
    all_events: list[dict] = []
    errors = 0
    for url in feeds:
        try:
            all_events.extend(parse_ics(_fetch(url)))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            errors += 1
    all_events.sort(key=lambda e: e.get("start") or "")
    data["cache"] = all_events
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    _save(data)
    msg = f"Обновил календарь: {len(all_events)} событий."
    if errors:
        msg += f" Ошибок загрузки: {errors}."
    return msg


def events_for_day(day: date | None = None) -> list[dict]:
    day = day or date.today()
    data = _load()
    cache = list(data.get("cache") or [])
    if not cache and data.get("feeds"):
        refresh_feeds()
        cache = list(_load().get("cache") or [])
    out: list[dict] = []
    for event in cache:
        try:
            start = datetime.fromisoformat(str(event.get("start")))
        except ValueError:
            continue
        if start.date() == day:
            out.append(event)
    return out


def today_events_text() -> str:
    events = events_for_day(date.today())
    if not events:
        feeds = _load().get("feeds") or []
        if not feeds:
            return "Календарь не подключён. Добавьте ICS-ссылку: добавь календарь <url>."
        return "На сегодня в календаре ничего нет."
    parts = []
    for event in events[:8]:
        try:
            start = datetime.fromisoformat(str(event["start"]))
            stamp = start.strftime("%H:%M") if (start.hour or start.minute) else "весь день"
        except ValueError:
            stamp = "?"
        parts.append(f"{stamp} — {event.get('summary', 'событие')}")
    return "Календарь на сегодня: " + "; ".join(parts) + "."


def upcoming_text(*, hours: int = 24) -> str:
    now = datetime.now()
    until = now + timedelta(hours=hours)
    data = _load()
    parts = []
    for event in data.get("cache") or []:
        try:
            start = datetime.fromisoformat(str(event.get("start")))
        except ValueError:
            continue
        if now <= start <= until:
            parts.append(f"{start.strftime('%H:%M')} — {event.get('summary')}")
    if not parts:
        return "Ближайших событий нет."
    return "Скоро: " + "; ".join(parts[:6]) + "."
