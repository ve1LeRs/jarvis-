"""Look up answers on the web and return a short spoken summary.

Sources (no API keys):
1. DuckDuckGo Instant Answer JSON
2. DuckDuckGo HTML snippets
3. Russian Wikipedia summary
4. Small built-in tips for common Windows how-tos
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from jarvis.actions import system as sys_act

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 JARVIS/1.0"
)

# Short, reliable tips when web snippets are weak.
_BUILTIN_TIPS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"раскладк|язык\s+ввода|keyboard\s+layout|смен[аыуе]\s+язык", re.I),
        (
            "В Windows раскладку клавиатуры обычно переключают сочетанием "
            "Win + пробел или Alt + Shift. "
            "Поменять сочетание можно в Параметры → Время и язык → Ввод → "
            "Дополнительные параметры клавиатуры → Сочетания клавиш для языков ввода."
        ),
    ),
    (
        re.compile(r"снимок\s+экрана|скриншот|screenshot", re.I),
        (
            "В Windows снимок всего экрана — клавиша Print Screen или Win + Print Screen "
            "(сохраняет в папку «Изображения → Screenshots»). "
            "Выделенную область — Win + Shift + S."
        ),
    ),
    (
        re.compile(r"диспетчер\s+задач|task\s+manager", re.I),
        "Диспетчер задач в Windows открывается сочетанием Ctrl + Shift + Esc.",
    ),
    (
        re.compile(r"блокир.*(экран|компьютер|пк)|lock\s+(screen|pc|computer)", re.I),
        "Чтобы заблокировать Windows, нажмите Win + L.",
    ),
]


@dataclass
class Answer:
    spoken: str
    source: str = ""
    url: str = ""
    opened_browser: bool = False


def _http_get(url: str, *, timeout: float = 12.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clip_for_speech(text: str, *, limit: int = 520) -> str:
    text = _clean_text(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer ending on a sentence boundary.
    for sep in (". ", "! ", "? ", "; "):
        idx = cut.rfind(sep)
        if idx >= int(limit * 0.45):
            return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0].strip() + "…"


def _builtin_tip(query: str) -> str | None:
    for pattern, tip in _BUILTIN_TIPS:
        if pattern.search(query):
            return tip
    return None


def _ddg_instant(query: str) -> Answer | None:
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
            "kl": "ru-ru",
        }
    )
    try:
        data = json.loads(_http_get(url, timeout=8))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    for key in ("Answer", "AbstractText", "Definition"):
        value = _clean_text(str(data.get(key) or ""))
        if len(value) >= 40:
            return Answer(
                spoken=_clip_for_speech(value),
                source="DuckDuckGo",
                url=str(data.get("AbstractURL") or data.get("AnswerURL") or ""),
            )

    related = data.get("RelatedTopics") or []
    for item in related:
        if not isinstance(item, dict):
            continue
        value = _clean_text(str(item.get("Text") or ""))
        if len(value) >= 40:
            return Answer(
                spoken=_clip_for_speech(value),
                source="DuckDuckGo",
                url=str((item.get("FirstURL") or "")),
            )
    return None


def _ddg_html_snippets(query: str) -> list[str]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        page = _http_get(url, timeout=12)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return []

    chunks = re.findall(
        r'class="result__snippet[^"]*"[^>]*>(.*?)</(?:a|td|div)',
        page,
        flags=re.S | re.I,
    )
    snippets: list[str] = []
    for chunk in chunks:
        text = _clean_text(chunk)
        if len(text) >= 40:
            snippets.append(text)
    return snippets[:4]


def _wikipedia_summary(query: str) -> Answer | None:
    # Skip pure how-to questions — wiki titles are often a poor match.
    if re.match(r"^(как|how)\b", query.strip(), flags=re.I):
        # Still try a tightened subject after "как"
        subject = re.sub(r"^(как|how)\s+", "", query.strip(), flags=re.I)
    else:
        subject = query

    search_url = "https://ru.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": subject,
            "format": "json",
            "srlimit": 1,
            "utf8": 1,
        }
    )
    try:
        payload = json.loads(_http_get(search_url, timeout=8))
        hits = (((payload.get("query") or {}).get("search")) or [])
        if not hits:
            return None
        title = hits[0].get("title") or ""
        if not title:
            return None
        summary_url = "https://ru.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(
            title
        )
        summary = json.loads(_http_get(summary_url, timeout=8))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, KeyError):
        return None

    extract = _clean_text(str(summary.get("extract") or ""))
    if len(extract) < 40:
        return None
    page_url = str(((summary.get("content_urls") or {}).get("desktop") or {}).get("page") or "")
    return Answer(
        spoken=_clip_for_speech(extract),
        source="Википедия",
        url=page_url,
    )


def _has_hotkey_advice(text: str) -> bool:
    t = (text or "").lower()
    return bool(
        re.search(
            r"(win\s*\+|⊞|\balt\s*\+\s*shift\b|\bshift\s*\+\s*alt\b|"
            r"\bctrl\s*\+|\bcontrol\s*\+|сочетани[ея]\s+клавиш)",
            t,
        )
    )


def _compose_from_snippets(query: str, snippets: list[str]) -> Answer | None:
    if not snippets:
        return None
    # Prefer snippet that mentions actionable keys / concrete advice.
    scored = sorted(
        snippets,
        key=lambda s: (
            _has_hotkey_advice(s)
            + ("параметр" in s.lower())
            + ("нажм" in s.lower())
            + ("переключ" in s.lower())
        ),
        reverse=True,
    )
    best = scored[0]
    tip = _builtin_tip(query)
    # Prefer curated tip for how-tos when web text has no real hotkey advice.
    if tip and (len(best) < 90 or not _has_hotkey_advice(best)):
        return Answer(spoken=tip, source="подсказка JARVIS")
    return Answer(spoken=_clip_for_speech(best), source="поиск")


def lookup(query: str, *, open_browser: bool = True) -> Answer:
    """Return a spoken answer for a user question / search topic."""
    q = _clean_text(query)
    if not q:
        return Answer(spoken="Уточните вопрос, сэр.")

    # 1) Instant answers
    answer = _ddg_instant(q)

    # 2) HTML snippets (best for how-to)
    if answer is None:
        answer = _compose_from_snippets(q, _ddg_html_snippets(q))

    # 3) Wikipedia for definitions / topics
    if answer is None or (
        answer
        and answer.source == "поиск"
        and re.match(r"^(что такое|кто такой|кто такая|расскажи про|объясни)\b", q, re.I)
    ):
        wiki = _wikipedia_summary(q)
        if wiki is not None:
            answer = wiki

    # 4) Built-in tips — also override weak/off-topic web answers for known how-tos
    tip = _builtin_tip(q)
    if tip:
        if answer is None or not _has_hotkey_advice(answer.spoken):
            # For how-to questions with a curated tip, prefer the tip.
            if answer is None or re.match(r"^(как|how)\b", q, flags=re.I):
                answer = Answer(spoken=tip, source="подсказка JARVIS")

    # Always offer a browser page for deeper reading when requested.
    search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}"
    opened = False
    if open_browser:
        try:
            sys_act.search_web(q)
            opened = True
        except Exception:
            try:
                sys_act.open_url(search_url)
                opened = True
            except Exception:
                opened = False

    if answer is None:
        spoken = (
            "Краткого ответа не нашёл. "
            + ("Открыл поиск в браузере — посмотрите результаты." if opened else "Попробуйте переформулировать вопрос.")
        )
        return Answer(spoken=spoken, source="", url=search_url, opened_browser=opened)

    preface = ""
    if answer.source == "Википедия":
        preface = "По данным Википедии: "
    elif answer.source.startswith("подсказка"):
        preface = ""
    else:
        preface = "Кратко: "

    spoken = preface + answer.spoken
    if opened:
        spoken = spoken.rstrip(".") + ". Подробности открыл в браузере."
    return Answer(
        spoken=_clip_for_speech(spoken, limit=650),
        source=answer.source,
        url=answer.url or search_url,
        opened_browser=opened,
    )


def is_question(text: str) -> bool:
    t = (text or "").strip().lower().replace("ё", "е")
    if not t:
        return False
    if t.endswith("?"):
        return True
    return bool(
        re.match(
            r"^(как|почему|зачем|зачем|чем|когда|где|откуда|сколько|что\s+такое|"
            r"кто\s+такой|кто\s+такая|расскажи|объясни|что\s+знач|what|how|why|when|where)\b",
            t,
        )
    )
