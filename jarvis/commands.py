"""Natural-language command router (Russian + English)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable

from jarvis import config
from jarvis import memory
from jarvis import reminders
from jarvis.actions import fun as fun_act
from jarvis.actions import spotify as spotify_act
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
    # YouTube search before generic search
    (re.compile(r"^(?:найди|поищи|поиск)\s+(?:на\s+)?(?:ютуб[еу]?|youtube)\s+(.+)$"), "youtube_search"),
    # Search
    (re.compile(r"^(?:найди|найти|поищи|поиск|загугли|google)\s+(?:информацию\s+о(?:б)?\s+|про\s+|о(?:б)?\s+)?(.+)$"), "search"),
    (re.compile(r"^(?:что\s+такое|кто\s+такой|кто\s+такая)\s+(.+)$"), "search"),
    (re.compile(r"^(?:search|look\s+up|find(?:\s+info(?:rmation)?)?(?:\s+about)?)\s+(.+)$"), "search"),
    (re.compile(r"^(?:погода)(?:\s+(?:в|во|для)\s+(.+))?$"), "weather"),
    # Notes / reminders / memory
    (re.compile(r"^(?:запиши|запомни|заметка|заметку)\s+(.+)$"), "note_add"),
    (re.compile(r"^(?:заметки|покажи\s+заметки|мои\s+заметки)$"), "note_list"),
    (re.compile(r"^(?:очисти\s+заметки|удали\s+заметки)$"), "note_clear"),
    (re.compile(r"^(?:через\s+\d+.+)$"), "remind"),
    (re.compile(r"^(?:напомни(?:ть)?\s+.+)$"), "remind"),
    (re.compile(r"^(?:напоминания|мои\s+напоминания)$"), "remind_list"),
    (re.compile(r"^(?:отмени\s+напоминания|очисти\s+напоминания)$"), "remind_clear"),
    (re.compile(r"^(?:повтори|ещё\s+раз|again|repeat)$"), "repeat"),
    (re.compile(r"^(?:история|последние\s+команды)$"), "history"),
    # Media / volume
    (re.compile(r"^(?:громче|увеличь\s+громкость|volume\s+up)$"), "vol_up"),
    (re.compile(r"^(?:тише|уменьши\s+громкость|volume\s+down)$"), "vol_down"),
    (re.compile(r"^(?:без\s+звука|выключи\s+звук|mute|мьют)$"), "vol_mute"),
    (re.compile(r"^(?:пауза|продолжи|play|pause|плей)$"), "media_pp"),
    (re.compile(r"^(?:следующий(?:\s+трек)?|next)$"), "media_next"),
    (re.compile(r"^(?:предыдущий(?:\s+трек)?|previous|prev)$"), "media_prev"),
    # Fun / utils
    (re.compile(r"^(?:анекдот|шутка|расскажи\s+шутку|joke)$"), "joke"),
    (re.compile(r"^(?:монетка|подбрось\s+монетку|орёл\s+или\s+решка)$"), "coin"),
    (re.compile(r"^(?:кубик|брось\s+кубик|dice)(?:\s+(\d+))?$"), "dice"),
    (re.compile(r"^(?:посчитай|вычисли|сколько\s+будет|calculate)\s+(.+)$"), "calc"),
    (re.compile(r"^(?:скриншот|сделай\s+скриншот|screenshot)$"), "screenshot"),
    (re.compile(r"^(?:буфер|что\s+в\s+буфере|clipboard)$"), "clipboard"),
    (re.compile(r"^(?:статус|состояние|system\s+status)$"), "status"),
    (re.compile(r"^(?:молчи|тихий\s+режим|выключи\s+голос|mute\s+voice)$"), "mute_on"),
    (re.compile(r"^(?:говори|включи\s+голос|unmute)$"), "mute_off"),
    # Spotify (before generic open / media)
    (
        re.compile(
            r"^(?:включи|поставь|поиграй|запусти|play)\s+(.+?)\s+"
            r"(?:в\s+)?(?:спотифай|spotify|спотифае)$"
        ),
        "spotify_play",
    ),
    (
        re.compile(
            r"^(?:в\s+)?(?:спотифай|spotify)\s+(?:включи|поставь|поиграй|найди|play)?\s*(.+)$"
        ),
        "spotify_play",
    ),
    (
        re.compile(
            r"^(?:включи|поставь|поиграй)\s+(?:песню|трек|музыку)\s+(.+)$"
        ),
        "spotify_play",
    ),
    (
        re.compile(
            r"^(?:из\s+медиатеки|в\s+медиатеке|из\s+любимых)\s+(.+)$"
        ),
        "spotify_library",
    ),
    (
        re.compile(
            r"^(?:включи|поставь|поиграй)\s+(.+?)\s+(?:из\s+медиатеки|из\s+любимых)$"
        ),
        "spotify_library",
    ),
    (
        re.compile(
            r"^(?:открой|открыть|запусти)\s+(?:спотифай|spotify)$"
        ),
        "spotify_open",
    ),
    (
        re.compile(
            r"^(?:открой|открыть)\s+(?:медиатеку|любимые(?:\s+треки)?|liked\s+songs)$"
        ),
        "spotify_liked",
    ),
    # Open explorer folders
    (re.compile(r"^(?:открой|открыть|запусти|запустить)\s+(?:проводник|explorer|файловый\s+менеджер|файлы)$"), "explorer"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?загрузки$"), "downloads"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?(?:рабочий\s+стол|desktop)$"), "desktop"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?(?:документы|documents)$"), "documents"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?(?:картинки|изображения|pictures)$"), "pictures"),
    (re.compile(r"^(?:открой|открыть)\s+(?:папку\s+)?(?:музыку|music)$"), "music"),
    # Open browser / chrome
    (re.compile(r"^(?:открой|открыть|запусти)\s+(?:хром|chrome|браузер)(?:\s+(.+))?$"), "chrome"),
    # Open named app / site
    (re.compile(r"^(?:открой|открыть|запусти|запустить)\s+(.+)$"), "open"),
    # Time / date
    (re.compile(r"^(?:который\s+час|сколько\s+времени|время|what\s+time)$"), "time"),
    (re.compile(r"^(?:какое\s+сегодня\s+число|какая\s+дата|дата|what\s+date)$"), "date"),
    # System power
    (re.compile(r"^(?:выключи(?:\s+компьютер)?|shutdown|выключение)$"), "shutdown"),
    (re.compile(r"^(?:перезагрузи(?:\s+компьютер)?|restart|reboot)$"), "restart"),
    (re.compile(r"^(?:сон|усни|sleep|спящий\s+режим)$"), "sleep"),
    (re.compile(r"^(?:отмена|отмени(?:\s+выключение)?|cancel)$"), "cancel_shutdown"),
    (re.compile(r"^(?:заблокируй|блокировка|lock)$"), "lock"),
    (re.compile(r"^(?:очисти\s+корзину|пустая\s+корзина|empty\s+recycle)$"), "recycle"),
    (re.compile(r"^(?:добавь\s+в\s+автозапуск|включи\s+автозапуск|autostart\s+on)$"), "autostart_on"),
    (re.compile(r"^(?:убери\s+из\s+автозапуска|выключи\s+автозапуск|autostart\s+off)$"), "autostart_off"),
    # Greetings / help
    (re.compile(r"^(?:привет|здравствуй|hello|hi)$"), "hello"),
    (re.compile(r"^(?:спасибо|благодарю|thanks)$"), "thanks"),
    (re.compile(r"^(?:помощь|help|что\s+ты\s+умеешь|команды)$"), "help"),
    (re.compile(r"^(?:пока|до\s+свидания|выключись|стоп|exit|quit)$"), "bye"),
]


def parse_and_run(command: str) -> Result:
    original = (command or "").strip()
    text = original.lower().replace("ё", "е")
    # Keep math operators for calculator commands; strip other punctuation.
    # Put '-' at the end of the class so it is not a range.
    text = re.sub(r"[^\w\s+*/().%-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return _fail()

    for pattern, action in _RULES:
        match = pattern.match(text)
        if not match:
            continue
        payload = (match.group(1) if match.lastindex else "") or ""
        payload = payload.strip()
        # Reminders need the fuller phrase (with numbers/units).
        if action == "remind":
            payload = text
        # Calculator: prefer original expression (operators may be spaced).
        if action == "calc":
            raw_match = re.search(
                r"(?:посчитай|вычисли|сколько\s+будет|calculate)\s+(.+)$",
                original,
                flags=re.IGNORECASE,
            )
            if raw_match:
                payload = raw_match.group(1).strip()
        result = _dispatch(action, payload, text)
        if result.ok and action not in {
            "repeat",
            "history",
            "help",
            "hello",
            "thanks",
            "bye",
            "mute_on",
            "mute_off",
            "note_list",
            "remind_list",
        }:
            memory.remember_command(original or text)
        return result

    # Soft fallback: if it looks like a search intent, search it.
    if any(w in text for w in ("найди", "поиск", "информац", "что такое")):
        cleaned = re.sub(
            r"^(?:джарвис|jarvis)?\s*(?:найди|поищи|поиск)?\s*(?:информацию\s+о(?:б)?)?\s*",
            "",
            text,
        ).strip()
        if cleaned:
            result = _dispatch("search", cleaned, text)
            if result.ok:
                memory.remember_command(original or text)
            return result

    return _fail()


def _dispatch(action: str, payload: str, raw: str) -> Result:
    if action == "search":
        msg = act.search_web(payload)
        return _ok(f"{random.choice(config.ACKNOWLEDGMENTS)} Ищу информацию о {payload}.", msg)

    if action == "youtube_search":
        return _ok(f"Ищу на YouTube: {payload}.", act.search_youtube(payload))

    if action == "weather":
        city = payload or None
        spoken = f"Смотрю погоду{(' в ' + city) if city else ''}."
        return _ok(spoken, act.open_weather(city))

    if action == "note_add":
        return _ok(memory.add_note(payload))

    if action == "note_list":
        return _ok(memory.list_notes())

    if action == "note_clear":
        return _ok(memory.clear_notes())

    if action == "remind":
        parsed = reminders.parse_delay(payload)
        if not parsed:
            return _fail("Скажите, например: через 5 минут проверить духовку.")
        seconds, body = parsed
        return _ok(reminders.schedule(seconds, body))

    if action == "remind_list":
        return _ok(reminders.list_reminders())

    if action == "remind_clear":
        return _ok(reminders.clear_reminders())

    if action == "repeat":
        last = memory.last_command()
        if not last:
            return _fail("Пока нечего повторять.")
        normalized_last = last.lower().replace("ё", "е").strip()
        if normalized_last in {"повтори", "ещё раз", "еще раз", "again", "repeat"}:
            return _fail("Последняя команда тоже была «повтори».")
        return parse_and_run(last)

    if action == "history":
        items = memory.recent_history()
        if not items:
            return _ok("История команд пуста.")
        return _ok("Последние команды: " + "; ".join(items))

    if action == "vol_up":
        return _ok(act.volume_up())

    if action == "vol_down":
        return _ok(act.volume_down())

    if action == "vol_mute":
        return _ok(act.volume_mute())

    if action == "media_pp":
        return _ok(act.media_play_pause())

    if action == "media_next":
        return _ok(act.media_next())

    if action == "media_prev":
        return _ok(act.media_prev())

    if action == "joke":
        return _ok(fun_act.joke())

    if action == "coin":
        return _ok(fun_act.coin_flip())

    if action == "dice":
        sides = int(payload) if payload.isdigit() else 6
        return _ok(fun_act.roll_dice(sides))

    if action == "calc":
        return _ok(fun_act.calculate(payload))

    if action == "screenshot":
        return _ok(act.take_screenshot())

    if action == "clipboard":
        return _ok(act.read_clipboard())

    if action == "status":
        return _ok(act.system_status())

    if action == "mute_on":
        memory.set_muted(True)
        return _ok("Хорошо. Буду отвечать тихо, без голоса.")

    if action == "mute_off":
        memory.set_muted(False)
        return _ok("Голос снова включён.")

    if action == "spotify_open":
        return _ok(spotify_act.open_spotify())

    if action == "spotify_liked":
        return _ok(spotify_act.open_liked_songs())

    if action == "spotify_play":
        return _ok(spotify_act.play_song(payload))

    if action == "spotify_library":
        return _ok(spotify_act.play_from_library(payload))

    if action == "explorer":
        return _ok(f"{random.choice(config.ACKNOWLEDGMENTS)} Открываю проводник.", act.open_explorer())

    if action == "downloads":
        return _ok("Открываю папку загрузок.", act.open_downloads())

    if action == "desktop":
        return _ok("Открываю рабочий стол.", act.open_desktop())

    if action == "documents":
        return _ok("Открываю документы.", act.open_documents())

    if action == "pictures":
        return _ok("Открываю картинки.", act.open_pictures())

    if action == "music":
        return _ok("Открываю музыку.", act.open_music())

    if action == "chrome":
        if payload:
            if payload in {"youtube", "ютуб", "ютубе"}:
                return _ok("Открываю YouTube.", act.open_url("https://www.youtube.com"))
            return _ok("Открываю Chrome с поиском.", act.search_web(payload))
        return _ok(random.choice(config.ACKNOWLEDGMENTS), act.open_chrome())

    if action == "open":
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
            "карты",
            "новости",
            "github",
            "гитхаб",
        }
        first = payload.split()[0] if payload else ""
        if payload in known_sites or first in known_sites:
            return _ok(
                random.choice(config.ACKNOWLEDGMENTS),
                act.open_app(payload if payload in known_sites else first),
            )
        wiki = re.match(r"^(?:википедию|wikipedia)\s+(?:про\s+|о(?:б)?\s+)?(.+)$", payload)
        if wiki:
            q = wiki.group(1)
            return _ok(f"Ищу {q} в Википедии.", act.search_web(f"site:wikipedia.org {q}"))
        # "открой погоду в москве"
        weather = re.match(r"^погод[ауе]\s+(?:в|во|для)\s+(.+)$", payload)
        if weather:
            city = weather.group(1)
            return _ok(f"Смотрю погоду в {city}.", act.open_weather(city))
        detail = act.open_app(payload)
        return _ok(f"{random.choice(config.ACKNOWLEDGMENTS)} {detail}", detail)

    if action == "time":
        return _ok(act.tell_time())

    if action == "date":
        return _ok(act.tell_date())

    if action == "shutdown":
        return _ok(act.shutdown_pc())

    if action == "restart":
        return _ok(act.restart_pc())

    if action == "sleep":
        return _ok(act.sleep_pc())

    if action == "cancel_shutdown":
        return _ok(act.cancel_shutdown())

    if action == "lock":
        return _ok(act.lock_pc())

    if action == "recycle":
        return _ok(act.empty_recycle_bin())

    if action == "autostart_on":
        from jarvis import autostart

        msg = autostart.enable_autostart()
        return _ok("Включил автозапуск. Буду стартовать вместе с Windows.", msg)

    if action == "autostart_off":
        from jarvis import autostart

        msg = autostart.disable_autostart()
        return _ok("Автозапуск отключён.", msg)

    if action == "hello":
        return _ok(random.choice(config.GREETINGS))

    if action == "thanks":
        return _ok("Всегда рад помочь, сэр.")

    if action == "help":
        help_text = (
            "Я умею искать в Google и YouTube, включать песни в Spotify, "
            "открывать приложения и папки, говорить время и дату, "
            "управлять громкостью, делать скриншоты, считать, шутить, "
            "вести заметки и напоминания, смотреть погоду, "
            "блокировать и перезагружать компьютер. "
            "Пример: джарвис, включи Bohemian Rhapsody в спотифай."
        )
        return _ok(help_text)

    if action == "bye":
        return Result(True, "До связи, сэр.", detail="__EXIT__")

    return _fail(f"Неизвестное действие для: {raw}")
