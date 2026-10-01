"""Natural-language command router (Russian + English)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable

from jarvis import config
from jarvis import confirm
from jarvis import context
from jarvis import facts
from jarvis import macros
from jarvis import memory
from jarvis import reminders
from jarvis.actions import calendar as cal
from jarvis.actions import chrome_app
from jarvis.actions import cursor_app
from jarvis.actions import discord_app
from jarvis.actions import fun as fun_act
from jarvis.actions import games
from jarvis.actions import knowledge
from jarvis.actions import screen
from jarvis.actions import spotify as spotify_act
from jarvis.actions import system as act
from jarvis.actions import word_app
from jarvis.actions import workflows
from jarvis import bridge
from jarvis import llm
from jarvis import paths
from jarvis import plugins
from jarvis import proactive
from jarvis import updater


@dataclass
class Result:
    ok: bool
    spoken: str
    detail: str = ""


Handler = Callable[[str], Result]


def _ok(spoken: str, detail: str = "") -> Result:
    return Result(True, context.adapt_speech(spoken), detail or spoken)


def _fail(spoken: str | None = None) -> Result:
    return Result(False, context.adapt_speech(spoken or random.choice(config.NOT_UNDERSTOOD)))


# Patterns are checked in order. Group 1 is usually the payload.
_RULES: list[tuple[re.Pattern[str], str]] = [
    # Macros first — "когда говорю" must not fall into Q&A.
    (
        re.compile(
            r"^(?:когда\s+говорю|если\s+говорю|запомни\s+макрос)\s+(.+)$"
        ),
        "macro_add",
    ),
    (re.compile(r"^(?:макросы|мои\s+макросы)$"), "macro_list"),
    (re.compile(r"^(?:удали\s+макрос)\s+(.+)$"), "macro_del"),
    # Long-term facts before «запомни …» notes and «что …» questions
    (re.compile(r"^(?:запомни|запомните)\s+(?:что|обо\s+мне|про\s+меня)\s+(.+)$"), "fact_add"),
    (
        re.compile(
            r"^(?:что\s+ты\s+(?:знаешь|помнишь)\s+(?:обо\s+мне|про\s+меня)"
            r"|что\s+ты\s+(?:обо\s+мне|про\s+меня)\s+(?:знаешь|помнишь)"
            r"|мои\s+факты|факты\s+обо\s+мне)$"
        ),
        "fact_list",
    ),
    (re.compile(r"^(?:забудь\s+все\s+(?:обо\s+мне|про\s+меня)|очисти\s+память)$"), "fact_clear"),
    (re.compile(r"^забудь\s+(?:что\s+|про\s+|об?\s+)?(.+)$"), "fact_forget"),
    # YouTube search before generic search
    (re.compile(r"^(?:найди|поищи|поиск)\s+(?:на\s+)?(?:ютуб[еу]?|youtube)\s+(.+)$"), "youtube_search"),
    # App path detection / on-screen find before generic «найди …»
    (re.compile(r"^(?:найди\s+программы|профиль\s+пк|detect\s+apps|автопоиск\s+программ)$"), "paths_detect"),
    (re.compile(r"^(?:где\s+программы|пути\s+программ|app\s+paths)$"), "paths_status"),
    (
        re.compile(
            r"^(?:найди\s+на\s+экране|где\s+на\s+экране|find\s+on\s+screen)\s+(.+)$"
        ),
        "find_on_screen",
    ),
    # Spoken web answers / questions (before generic search)
    (
        re.compile(
            r"^(?:как|почему|зачем|чем|где|откуда|what|how|why|where)\b(.+)$"
        ),
        "answer",
    ),
    # "когда" as a question, but not "когда говорю"
    (
        re.compile(
            r"^(?:когда)\b(?!\s+говорю)(.+)$"
        ),
        "answer",
    ),
    (
        re.compile(
            r"^(?:расскажи(?:\s+мне)?(?:\s+про|\s+о(?:б)?)?|объясни(?:\s+мне)?(?:\s+про|\s+о(?:б)?)?)\s+(.+)$"
        ),
        "answer",
    ),
    (re.compile(r"^(?:что\s+такое|кто\s+такой|кто\s+такая|что\s+знач(?:ит)?)\s+(.+)$"), "answer"),
    # Search — also answers aloud + opens browser
    (re.compile(r"^(?:найди|найти|поищи|поиск|загугли|google)\s+(?:информацию\s+о(?:б)?\s+|про\s+|о(?:б)?\s+)?(.+)$"), "search"),
    (re.compile(r"^(?:search|look\s+up|find(?:\s+info(?:rmation)?)?(?:\s+about)?)\s+(.+)$"), "search"),
    (re.compile(r"^(?:погода)(?:\s+(?:в|во|для)\s+(.+))?$"), "weather"),
    # Discord voice memory before generic «запомни …» notes
    (
        re.compile(
            r"^(?:запомни\s+войс(?:\s+канал)?|discord\s+voice)\s+(.+)$"
        ),
        "discord_voice_save",
    ),
    (
        re.compile(
            r"^(?:зайди\s+в\s+войс|войди\s+в\s+войс|join\s+voice|голосовой\s+канал)\s*(.*)$"
        ),
        "discord_voice",
    ),
    # Notes / reminders / memory
    (re.compile(r"^(?:запиши|запомни|заметка|заметку)\s+(.+)$"), "note_add"),
    (re.compile(r"^(?:заметки|покажи\s+заметки|мои\s+заметки)$"), "note_list"),
    (re.compile(r"^(?:очисти\s+заметки|удали\s+заметки)$"), "note_clear"),
    (re.compile(r"^(?:через\s+\d+.+)$"), "remind"),
    (re.compile(r"^(?:напомни(?:ть)?\s+.+)$"), "remind"),
    (re.compile(r"^(?:в|во)\s+\d{1,2}(?:[:.\s]\d{2})?\s+.+$"), "remind"),
    (re.compile(r"^(?:напоминания|мои\s+напоминания)$"), "remind_list"),
    (re.compile(r"^(?:отмени\s+напоминания|очисти\s+напоминания)$"), "remind_clear"),
    # Todos / daily brief
    (re.compile(r"^(?:добавь\s+в\s+дела|новое\s+дело|todo)\s+(.+)$"), "todo_add"),
    (re.compile(r"^(?:дела|список\s+дел|мои\s+дела|todos?)$"), "todo_list"),
    (re.compile(r"^(?:сделал|готово|выполнил(?:\s+дело)?)\s*(.*)$"), "todo_done"),
    (re.compile(r"^(?:что\s+сегодня|брифинг|на\s+сегодня|today)$"), "today"),
    # Calendar
    (re.compile(r"^(?:добавь\s+календарь|подключи\s+календарь|calendar\s+add)\s+(.+)$"), "cal_add"),
    (re.compile(r"^(?:календарь|мой\s+календарь|события\s+сегодня|что\s+в\s+календаре)$"), "cal_today"),
    (re.compile(r"^(?:обнови\s+календарь|синхронизируй\s+календарь)$"), "cal_refresh"),
    (re.compile(r"^(?:календари|список\s+календарей)$"), "cal_list"),
    (re.compile(r"^(?:очисти\s+календари|удали\s+календари)$"), "cal_clear"),
    # Screen / selection / OCR click
    (re.compile(r"^(?:прочитай\s+выделение|что\s+в\s+выделении|read\s+selection)$"), "read_selection"),
    (re.compile(r"^(?:что\s+на\s+экране|прочитай\s+экран|whats?\s+on\s+screen)$"), "read_screen"),
    (
        re.compile(
            r"^(?:опиши\s+экран|что\s+ты\s+видишь|vision|осмотри\s+экран)(?:\s+(.+))?$"
        ),
        "describe_screen",
    ),
    (
        re.compile(
            r"^(?:нажми|кликни|click)\s+(?:на\s+)?(?:кнопку\s+|текст\s+)?(.+)$"
        ),
        "click_text",
    ),
    # Confirmations
    (re.compile(r"^(?:подтверди|подтверждаю|точно|да\s+подтверди|confirm)$"), "confirm"),
    (re.compile(r"^(?:повтори|ещё\s+раз|again|repeat)$"), "repeat"),
    (re.compile(r"^(?:история|последние\s+команды)$"), "history"),
    (re.compile(r"^(?:контекст|какой\s+режим|status\s+mode)$"), "ctx_status"),
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
    # Workflows / modes
    (re.compile(r"^(?:рабочий\s+режим|режим\s+работы|work\s+mode)$"), "mode_work"),
    (re.compile(r"^(?:режим\s+кода|coding\s+mode)$"), "mode_code"),
    (re.compile(r"^(?:чилл(?:\s+режим)?|режим\s+чилл|chill\s+mode)$"), "mode_chill"),
    (re.compile(r"^(?:утренний\s+режим|доброе\s+утро|morning\s+mode)$"), "mode_morning"),
    (re.compile(r"^(?:вечерний\s+режим|добрый\s+вечер|evening\s+mode)$"), "mode_evening"),
    (
        re.compile(
            r"^(?:с\s+друзьями|с\s+другой|friends)\s+"
            r"(.+)$"
        ),
        "mode_friends",
    ),
    (
        re.compile(
            r"^(?:игровой\s+режим|го\s+в|режим\s+игры|game\s+mode)\s+"
            r"(.+)$"
        ),
        "mode_game",
    ),
    (re.compile(r"^(?:го\s+в\s+кс(?:\s*2)?|погнали\s+в\s+кс(?:\s*2)?)$"), "launch_cs2"),
    (re.compile(r"^(?:го\s+в\s+пабг|погнали\s+в\s+пабг)$"), "launch_pubg"),
    (re.compile(r"^(?:мой\s+стек|мои\s+программы|любимые\s+программы)$"), "stack"),
    # Spotify extras
    (re.compile(r"^(?:плейлист|открой\s+плейлист)\s+(.+)$"), "spotify_playlist"),
    (re.compile(r"^(?:моя\s+волна|радио\s+спотифай|spotify\s+radio)$"), "spotify_wave"),
    (re.compile(r"^(?:громче\s+спотифай|spotify\s+volume\s+up)$"), "spotify_vol_up"),
    (re.compile(r"^(?:тише\s+спотифай|spotify\s+volume\s+down)$"), "spotify_vol_down"),
    # Discord
    (re.compile(r"^(?:открой|открыть|запусти)\s+(?:дискорд|discord)$"), "discord_open"),
    (re.compile(r"^(?:мют|мут|замьють|размьють|mute)\s*(?:дискорд|discord)?$"), "discord_mute"),
    (re.compile(r"^(?:деф|дефнуть|undeafen|deafen)\s*(?:дискорд|discord)?$"), "discord_deafen"),
    (re.compile(r"^(?:дискорд|discord)\s+(?:инвайт|invite)\s+(.+)$"), "discord_invite"),
    # Spotify OAuth / queue
    (re.compile(r"^(?:настрой\s+спотифай|spotify\s+setup|spotify\s+login|войти\s+в\s+спотифай)$"), "spotify_oauth"),
    (re.compile(r"^(?:статус\s+спотифай|spotify\s+status)$"), "spotify_oauth_status"),
    (
        re.compile(
            r"^(?:сохрани\s+спотифай\s+ключи|spotify\s+keys)\s+(.+)$"
        ),
        "spotify_keys",
    ),
    (re.compile(r"^(?:в\s+очередь|добавь\s+в\s+очередь|queue)\s+(.+)$"), "spotify_queue"),
    # Game match / exit
    (
        re.compile(
            r"^(?:матч|режим\s+матча|match\s+mode)\s+(.+)$"
        ),
        "mode_match",
    ),
    (
        re.compile(
            r"^(?:выйди\s+из\s+игры|выход\s+из\s+игрового\s+режима|exit\s+game|закончи\s+матч)$"
        ),
        "mode_exit_game",
    ),
    # Proactive / paths / plugins / LLM
    (re.compile(r"^(?:проактивность\s+вкл|включи\s+проактивность)$"), "proactive_on"),
    (re.compile(r"^(?:проактивность\s+выкл|выключи\s+проактивность)$"), "proactive_off"),
    (re.compile(r"^(?:проактивность|proactive\s+status)$"), "proactive_status"),
    (re.compile(r"^(?:плагины|мои\s+плагины|plugins)$"), "plugins_list"),
    (re.compile(r"^(?:перезагрузи\s+плагины|reload\s+plugins)$"), "plugins_reload"),
    (re.compile(r"^(?:статус\s+модели|llm\s+status|олл[аа]ма)$"), "llm_status"),
    (re.compile(r"^(?:спроси\s+модель|локальная\s+модель)\s+(.+)$"), "llm_ask"),
    (re.compile(r"^(?:push\s+to\s+talk|ptt|горячая\s+клавиша)$"), "ptt_help"),
    # Phone bridge (Telegram / WhatsApp HTTP)
    (
        re.compile(
            r"^(?:сохрани\s+телеграм\s+токен|telegram\s+token)\s+(.+)$"
        ),
        "bridge_tg_token",
    ),
    (
        re.compile(
            r"^(?:разреши\s+телеграм\s+чат|allow\s+telegram\s+chat)\s+(.+)$"
        ),
        "bridge_tg_allow",
    ),
    (
        re.compile(
            r"^(?:включи\s+телеграм\s+мост|telegram\s+bridge\s+on|старт\s+телеграм\s+мост)$"
        ),
        "bridge_tg_on",
    ),
    (
        re.compile(
            r"^(?:выключи\s+телеграм\s+мост|telegram\s+bridge\s+off)$"
        ),
        "bridge_tg_off",
    ),
    (
        re.compile(
            r"^(?:включи\s+мост|мост\s+вкл|bridge\s+on|включи\s+телефонный\s+мост)$"
        ),
        "bridge_on",
    ),
    (
        re.compile(
            r"^(?:выключи\s+мост|мост\s+выкл|bridge\s+off)$"
        ),
        "bridge_off",
    ),
    (re.compile(r"^(?:статус\s+моста|мост|bridge\s+status)$"), "bridge_status"),
    (re.compile(r"^(?:секрет\s+моста|bridge\s+secret)\s+(.+)$"), "bridge_secret"),
    (
        re.compile(
            r"^(?:сохрани\s+ватсап|whatsapp\s+cloud)\s+(.+)$"
        ),
        "bridge_wa",
    ),
    # Chrome extras
    (re.compile(r"^(?:новая\s+вкладка|new\s+tab)(?:\s+(.+))?$"), "chrome_new_tab"),
    (re.compile(r"^(?:закрой\s+вкладку|close\s+tab)$"), "chrome_close_tab"),
    (re.compile(r"^(?:верни\s+вкладку|reopen\s+tab)$"), "chrome_reopen_tab"),
    (re.compile(r"^(?:обнови\s+страницу|refresh)$"), "chrome_refresh"),
    (re.compile(r"^(?:инкогнито|открой\s+инкогнито)(?:\s+(.+))?$"), "chrome_incognito"),
    (re.compile(r"^(?:открой\s+в\s+хроме|open\s+in\s+chrome)\s+(.+)$"), "chrome_site"),
    # Games
    (
        re.compile(
            r"^(?:запусти|запускай|открой|открыть|play)\s+"
            r"(?:кс(?:\s*2)?|cs(?:\s*2)?|counter-strike(?:\s*2)?|контра)$"
        ),
        "launch_cs2",
    ),
    (
        re.compile(
            r"^(?:запусти|запускай|открой|открыть|play)\s+"
            r"(?:пабг|pubg|пабджи|пубг|battlegrounds)$"
        ),
        "launch_pubg",
    ),
    # Bare game names (macros often map to just «пабг» / «кс»)
    (re.compile(r"^(?:кс(?:\s*2)?|cs(?:\s*2)?|counter-strike(?:\s*2)?|контра)$"), "launch_cs2"),
    (re.compile(r"^(?:пабг|pubg|пабджи|пубг|battlegrounds)$"), "launch_pubg"),
    # Cursor
    (re.compile(r"^(?:открой|открыть|запусти)\s+(?:курсор|cursor)(?:\s+(.+))?$"), "cursor_open"),
    (re.compile(r"^(?:новое\s+окно\s+курсора|cursor\s+new\s+window)$"), "cursor_new"),
    (re.compile(r"^(?:открой\s+джарвис(?:а)?\s+в\s+курсоре)$"), "cursor_jarvis"),
    # Word
    (re.compile(r"^(?:открой|открыть|запусти)\s+(?:ворд|word|microsoft\s+word)(?:\s+(.+))?$"), "word_open"),
    (re.compile(r"^(?:новый\s+документ|создай\s+документ|new\s+document)$"), "word_new"),
    (re.compile(r"^(?:сохрани\s+документ|save\s+document)$"), "word_save"),
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
    # Self-update (git pull) — no zip re-download
    (
        re.compile(
            r"^(?:обнови(?:сь|ться)?(?:\s+джарвис)?|обнови\s+код|update(?:\s+jarvis)?|git\s+pull)$"
        ),
        "self_update",
    ),
    (re.compile(r"^(?:версия|какой\s+коммит|git\s+status|update\s+status)$"), "update_status"),
    # Greetings / help
    (re.compile(r"^(?:привет|здравствуй|hello|hi)$"), "hello"),
    (re.compile(r"^(?:спасибо|благодарю|thanks)$"), "thanks"),
    (re.compile(r"^(?:помощь|help|что\s+ты\s+умеешь|команды)$"), "help"),
    (re.compile(r"^(?:пока|до\s+свидания|выключись|стоп|exit|quit)$"), "bye"),
]


def parse_and_run(command: str, *, _depth: int = 0) -> Result:
    original = (command or "").strip()
    text = original.lower().replace("ё", "е")
    # Keep math operators for calculator commands; strip other punctuation.
    # Put '-' at the end of the class so it is not a range.
    text = re.sub(r"[^\w\s+*/().%-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return _fail()

    # Custom macros win early (exact phrase match).
    if _depth < 3:
        mapped = macros.resolve(text)
        if mapped and macros.normalize_phrase(mapped) != text:
            return parse_and_run(mapped, _depth=_depth + 1)

    # «как меня зовут», «когда мой день рождения» — answer from remembered facts.
    remembered = facts.answer(text)
    if remembered:
        return _ok(remembered, "facts")

    for pattern, action in _RULES:
        match = pattern.match(text)
        if not match:
            continue
        payload = (match.group(1) if match.lastindex else "") or ""
        payload = payload.strip()
        # Reminders need the original phrase (keep "18:00" colons).
        if action == "remind":
            payload = original.lower().replace("ё", "е")
        # Calculator: prefer original expression (operators may be spaced).
        if action == "calc":
            raw_match = re.search(
                r"(?:посчитай|вычисли|сколько\s+будет|calculate)\s+(.+)$",
                original,
                flags=re.IGNORECASE,
            )
            if raw_match:
                payload = raw_match.group(1).strip()
        # Macros also need original separators.
        if action == "macro_add":
            payload = original.lower().replace("ё", "е")
        # Facts keep the user's casing (names, brands).
        if action == "fact_add":
            raw_match = re.search(
                r"(?:запомни|запомните)[\s,]+(?:что|обо\s+мне|про\s+меня)[\s,:—-]+(.+)$",
                original,
                flags=re.IGNORECASE,
            )
            if raw_match:
                payload = raw_match.group(1).strip()
        # Calendar ICS URLs keep : / characters from the original line.
        if action == "cal_add":
            raw_match = re.search(
                r"(?:добавь\s+календарь|подключи\s+календарь|calendar\s+add)\s+(.+)$",
                original,
                flags=re.IGNORECASE,
            )
            if raw_match:
                payload = raw_match.group(1).strip()
        # Tokens/secrets often contain ':' — keep original tail.
        if action in {"bridge_tg_token", "bridge_secret", "bridge_wa", "spotify_keys"}:
            patterns = {
                "bridge_tg_token": r"(?:сохрани\s+телеграм\s+токен|telegram\s+token)\s+(.+)$",
                "bridge_secret": r"(?:секрет\s+моста|bridge\s+secret)\s+(.+)$",
                "bridge_wa": r"(?:сохрани\s+ватсап|whatsapp\s+cloud)\s+(.+)$",
                "spotify_keys": r"(?:сохрани\s+спотифай\s+ключи|spotify\s+keys)\s+(.+)$",
            }
            raw_match = re.search(patterns[action], original, flags=re.IGNORECASE)
            if raw_match:
                payload = raw_match.group(1).strip()
        dispatch_raw = (
            payload
            if action in {"remind", "macro_add", "cal_add", "bridge_tg_token", "bridge_secret", "bridge_wa", "spotify_keys"}
            else text
        )
        result = _dispatch(action, payload, dispatch_raw)
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

    # Plugins before soft fallback.
    plugin_hit = plugins.match_and_run(text)
    if plugin_hit is not None:
        ok, spoken = plugin_hit
        result = Result(ok, context.adapt_speech(spoken), spoken)
        if ok:
            memory.remember_command(original or text)
        return result

    # Local LLM: follow-ups and free-form routing.
    if _depth < 2 and (llm.looks_like_followup(text) or len(text.split()) >= 4):
        if llm.looks_like_followup(text):
            answered = llm.answer(text)
            if answered:
                memory.remember_command(original or text)
                return _ok(answered, "llm")
        routed = llm.route_command(text)
        if routed and macros.normalize_phrase(routed) != text:
            return parse_and_run(routed, _depth=_depth + 1)

    # Soft fallback: questions / search-like phrases.
    if knowledge.is_question(text) or any(
        w in text for w in ("найди", "поиск", "информац", "что такое", "расскажи", "объясни")
    ):
        cleaned = re.sub(
            r"^(?:джарвис|jarvis)?\s*(?:найди|поищи|поиск)?\s*(?:информацию\s+о(?:б)?)?\s*",
            "",
            text,
        ).strip()
        if cleaned:
            # Prefer local LLM answer when available for open questions.
            answered = llm.answer(cleaned) if knowledge.is_question(text) else None
            if answered:
                memory.remember_command(original or text)
                return _ok(answered, "llm")
            action = "answer" if knowledge.is_question(text) else "search"
            result = _dispatch(action, cleaned, text)
            if result.ok:
                memory.remember_command(original or text)
            return result

    return _fail()


def _dispatch(action: str, payload: str, raw: str) -> Result:
    if action == "answer":
        query = (payload or raw or "").strip()
        # Patterns capture the tail after "как" without the leading word — restore it.
        if re.match(r"^(как|почему|зачем|чем|когда|где|откуда|what|how|why|when|where)\b", raw):
            query = raw
        found = knowledge.lookup(query, open_browser=True)
        return _ok(found.spoken, found.source or found.url)

    if action == "search":
        found = knowledge.lookup(payload, open_browser=True)
        return _ok(found.spoken, found.source or found.url)

    if action == "youtube_search":
        return _ok(f"Ищу на YouTube: {payload}.", act.search_youtube(payload))

    if action == "weather":
        city = payload or None
        spoken = f"Смотрю погоду{(' в ' + city) if city else ''}."
        return _ok(spoken, act.open_weather(city))

    if action == "fact_add":
        return _ok(facts.add(payload))

    if action == "fact_list":
        return _ok(facts.list_text())

    if action == "fact_clear":
        ok, spoken, detail = confirm.ask(
            "fact_clear",
            "стереть всё, что я о вас знаю",
            lambda: (True, facts.clear(), ""),
        )
        return Result(ok, context.adapt_speech(spoken), detail)

    if action == "fact_forget":
        return _ok(facts.forget(payload))

    if action == "note_add":
        return _ok(memory.add_note(payload))

    if action == "note_list":
        return _ok(memory.list_notes())

    if action == "note_clear":
        return _ok(memory.clear_notes())

    if action == "remind":
        parsed = reminders.parse_when(payload)
        if not parsed:
            return _fail("Скажите, например: через 5 минут чай — или напомни в 18:00 созвон.")
        when, body = parsed
        return _ok(reminders.schedule_at(when, body))

    if action == "remind_list":
        return _ok(reminders.list_reminders())

    if action == "remind_clear":
        return _ok(reminders.clear_reminders())

    if action == "todo_add":
        return _ok(memory.add_todo(payload))

    if action == "todo_list":
        return _ok(memory.list_todos())

    if action == "todo_done":
        return _ok(memory.complete_todo(payload))

    if action == "today":
        return _ok(memory.today_brief())

    if action == "cal_add":
        return _ok(cal.add_feed(payload))

    if action == "cal_today":
        return _ok(cal.today_events_text())

    if action == "cal_refresh":
        return _ok(cal.refresh_feeds())

    if action == "cal_list":
        return _ok(cal.list_feeds())

    if action == "cal_clear":
        return _ok(cal.clear_feeds())

    if action == "macro_add":
        parsed = macros.parse_learn(payload or raw)
        if not parsed:
            return _fail("Скажите: когда говорю погнали — запусти пабг.")
        phrase, command = parsed
        return _ok(macros.add_macro(phrase, command))

    if action == "macro_list":
        return _ok(macros.list_macros())

    if action == "macro_del":
        return _ok(macros.remove_macro(payload))

    if action == "read_selection":
        return _ok(screen.read_selection())

    if action == "read_screen":
        return _ok(screen.whats_on_screen())

    if action == "describe_screen":
        return _ok(screen.describe_screen(payload or None))

    if action == "find_on_screen":
        return _ok(screen.find_on_screen(payload))

    if action == "click_text":
        return _ok(screen.click_text(payload))

    if action == "confirm":
        ok, spoken, detail = confirm.confirm()
        return Result(ok, context.adapt_speech(spoken), detail)

    if action == "ctx_status":
        return _ok(context.status_text())

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

    if action == "mode_work":
        return _ok(workflows.work_mode())

    if action == "mode_code":
        return _ok(workflows.coding_mode())

    if action == "mode_chill":
        return _ok(workflows.chill_mode())

    if action == "mode_morning":
        return _ok(workflows.morning_mode())

    if action == "mode_evening":
        return _ok(workflows.evening_mode())

    if action == "mode_friends":
        return _ok(games.friends_mode(payload))

    if action == "mode_game":
        return _ok(games.game_mode(payload))

    if action == "stack":
        return _ok(workflows.stack_status())

    if action == "spotify_playlist":
        return _ok(spotify_act.play_playlist_api(payload))

    if action == "spotify_wave":
        return _ok(spotify_act.open_radio_or_wave())

    if action == "spotify_vol_up":
        return _ok(spotify_act.focus_spotify_volume("up"))

    if action == "spotify_vol_down":
        return _ok(spotify_act.focus_spotify_volume("down"))

    if action == "spotify_oauth":
        return _ok(spotify_act.start_oauth_login())

    if action == "spotify_oauth_status":
        return _ok(spotify_act.oauth_status())

    if action == "spotify_keys":
        parts = (payload or "").split()
        if len(parts) >= 2:
            return _ok(spotify_act.save_client_credentials(parts[0], parts[1]))
        return _fail("Скажите: сохрани спотифай ключи CLIENT_ID CLIENT_SECRET")

    if action == "spotify_queue":
        return _ok(spotify_act.queue_song(payload))

    if action == "discord_open":
        return _ok(discord_app.open_discord())

    if action == "discord_mute":
        return _ok(discord_app.toggle_mute())

    if action == "discord_deafen":
        return _ok(discord_app.toggle_deafen())

    if action == "discord_invite":
        return _ok(discord_app.join_invite(payload))

    if action == "discord_voice":
        return _ok(discord_app.join_voice_channel(payload or None))

    if action == "discord_voice_save":
        return _ok(discord_app.remember_voice_channel(payload))

    if action == "mode_match":
        return _ok(games.match_mode(payload))

    if action == "mode_exit_game":
        return _ok(games.exit_game_mode())

    if action == "proactive_on":
        return _ok(proactive.enable(True))

    if action == "proactive_off":
        return _ok(proactive.enable(False))

    if action == "proactive_status":
        return _ok(proactive.status_text())

    if action == "paths_detect":
        found = paths.detect_all()
        return _ok(f"Нашёл программ: {len(found)}. " + paths.status_text())

    if action == "paths_status":
        return _ok(paths.status_text())

    if action == "plugins_list":
        return _ok(plugins.list_plugins())

    if action == "plugins_reload":
        return _ok(plugins.reload())

    if action == "llm_status":
        return _ok(llm.status_text())

    if action == "llm_ask":
        answered = llm.answer(payload)
        if answered:
            return _ok(answered, "llm")
        return _fail(llm.status_text())

    if action == "ptt_help":
        from jarvis import hotkeys

        return _ok(hotkeys.describe_default())

    if action == "bridge_tg_token":
        return _ok(bridge.save_telegram_token(payload))

    if action == "bridge_tg_allow":
        return _ok(bridge.allow_telegram_chat(payload))

    if action == "bridge_tg_on":
        return _ok(bridge.start_telegram())

    if action == "bridge_tg_off":
        return _ok(bridge.stop_telegram())

    if action == "bridge_on":
        return _ok(bridge.start_all())

    if action == "bridge_off":
        return _ok(bridge.stop_all())

    if action == "bridge_status":
        return _ok(bridge.status_text())

    if action == "bridge_secret":
        return _ok(bridge.save_http_secret(payload))

    if action == "bridge_wa":
        parts = (payload or "").split()
        if len(parts) >= 2:
            verify = parts[2] if len(parts) >= 3 else "jarvis"
            return _ok(bridge.save_whatsapp_cloud(parts[0], parts[1], verify_token=verify))
        m = re.search(r"(\S+)\s+(\S+)(?:\s+(\S+))?$", raw or "")
        if m:
            return _ok(
                bridge.save_whatsapp_cloud(
                    m.group(1), m.group(2), verify_token=m.group(3) or "jarvis"
                )
            )
        return _fail("Скажите: сохрани ватсап TOKEN PHONE_NUMBER_ID [verify_token]")

    if action == "chrome_new_tab":
        return _ok(chrome_app.new_tab(payload or None))

    if action == "chrome_close_tab":
        return _ok(chrome_app.close_tab())

    if action == "chrome_reopen_tab":
        return _ok(chrome_app.reopen_tab())

    if action == "chrome_refresh":
        return _ok(chrome_app.refresh())

    if action == "chrome_incognito":
        return _ok(chrome_app.incognito(payload or None))

    if action == "chrome_site":
        return _ok(chrome_app.open_site(payload))

    if action == "launch_cs2":
        return _ok(games.launch_cs2())

    if action == "launch_pubg":
        return _ok(games.launch_pubg())

    if action == "cursor_open":
        return _ok(cursor_app.open_cursor(payload or None))

    if action == "cursor_new":
        return _ok(cursor_app.new_window())

    if action == "cursor_jarvis":
        return _ok(cursor_app.open_jarvis_repo())

    if action == "word_open":
        return _ok(word_app.open_word(payload or None))

    if action == "word_new":
        return _ok(word_app.new_document())

    if action == "word_save":
        return _ok(word_app.save_document())

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
            return _ok(chrome_app.open_site(payload))
        return _ok(random.choice(config.ACKNOWLEDGMENTS), chrome_app.open_chrome())

    if action == "open":
        # Route favorite stack apps through dedicated helpers.
        key = payload.strip().lower()
        favorites = {
            "дискорд": discord_app.open_discord,
            "discord": discord_app.open_discord,
            "курсор": cursor_app.open_cursor,
            "cursor": cursor_app.open_cursor,
            "ворд": word_app.open_word,
            "word": word_app.open_word,
            "кс": games.launch_cs2,
            "кс2": games.launch_cs2,
            "cs": games.launch_cs2,
            "cs2": games.launch_cs2,
            "пабг": games.launch_pubg,
            "pubg": games.launch_pubg,
            "спотифай": spotify_act.open_spotify,
            "spotify": spotify_act.open_spotify,
        }
        if key in favorites:
            return _ok(favorites[key]())

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
            "chatgpt",
            "чатгпт",
        }
        first = payload.split()[0] if payload else ""
        if payload in known_sites or first in known_sites:
            return _ok(
                random.choice(config.ACKNOWLEDGMENTS),
                chrome_app.open_site(payload if payload in known_sites else first),
            )
        wiki = re.match(r"^(?:википедию|wikipedia)\s+(?:про\s+|о(?:б)?\s+)?(.+)$", payload)
        if wiki:
            q = wiki.group(1)
            return _ok(f"Ищу {q} в Википедии.", act.search_web(f"site:wikipedia.org {q}"))
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
        ok, spoken, detail = confirm.ask(
            "shutdown",
            "выключить компьютер через 60 секунд",
            lambda: (True, act.shutdown_pc(), ""),
        )
        return Result(ok, context.adapt_speech(spoken), detail)

    if action == "restart":
        ok, spoken, detail = confirm.ask(
            "restart",
            "перезагрузить компьютер через 60 секунд",
            lambda: (True, act.restart_pc(), ""),
        )
        return Result(ok, context.adapt_speech(spoken), detail)

    if action == "sleep":
        ok, spoken, detail = confirm.ask(
            "sleep",
            "усыпить компьютер",
            lambda: (True, act.sleep_pc(), ""),
        )
        return Result(ok, context.adapt_speech(spoken), detail)

    if action == "cancel_shutdown":
        ok, spoken, detail = confirm.cancel_pending()
        if ok:
            # Also abort OS shutdown if it was already armed.
            os_msg = act.cancel_shutdown()
            return _ok(f"{spoken} {os_msg}")
        return _ok(act.cancel_shutdown())

    if action == "lock":
        return _ok(act.lock_pc())

    if action == "recycle":
        ok, spoken, detail = confirm.ask(
            "recycle",
            "очистить корзину",
            lambda: (True, act.empty_recycle_bin(), ""),
        )
        return Result(ok, context.adapt_speech(spoken), detail)

    if action == "autostart_on":
        from jarvis import autostart

        msg = autostart.enable_autostart()
        return _ok("Включил автозапуск. Буду стартовать вместе с Windows.", msg)

    if action == "autostart_off":
        from jarvis import autostart

        msg = autostart.disable_autostart()
        return _ok("Автозапуск отключён.", msg)

    if action == "self_update":
        return _ok(updater.update_from_git())

    if action == "update_status":
        return _ok(updater.status_text())

    if action == "hello":
        return _ok(random.choice(config.GREETINGS))

    if action == "thanks":
        return _ok("Всегда рад помочь, сэр.")

    if action == "help":
        help_text = (
            "Стек: Discord, Chrome, Spotify, CS2, PUBG, Cursor, Word. "
            "Режимы: утренний, вечерний, рабочий, матч, с друзьями. "
            "Календарь ICS, дела, напоминания, макросы, OCR/vision «опиши экран», "
            "память «запомни, что …» и «что ты обо мне знаешь», "
            "Spotify OAuth, войс Discord, плагины, Ollama, мост Telegram/WhatsApp, "
            "push-to-talk Ctrl+Alt+J, «обнови джарвис» без перекачки. "
            "Опасные команды — только после «подтверди»."
        )
        return _ok(help_text)

    if action == "bye":
        return Result(True, "До связи, сэр.", detail="__EXIT__")

    return _fail(f"Неизвестное действие для: {raw}")
