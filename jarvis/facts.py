"""Long-term facts about the user: «запомни, что …», «что ты обо мне знаешь»."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from jarvis import memory

MAX_FACTS = 200
PROMPT_FACTS = 30

_STOP_WORDS = {
    "мой", "моя", "мое", "мои", "моего", "моей", "моих", "моему", "моим",
    "меня", "мне", "мной", "я", "у", "ты", "вы", "это", "как", "какой",
    "какая", "какое", "какие", "каким", "когда", "где", "кто", "что", "чем",
    "сколько", "ли", "же", "а", "и", "в", "на", "за", "про", "о", "об", "не",
    "есть", "был", "была", "было", "будет", "знаешь", "помнишь", "скажи",
}
_PERSONAL = re.compile(r"\b(?:мой|моя|мое|мои|моего|моей|моих|меня|мне|я)\b")
_QUESTION = re.compile(r"^(?:как|какой|какая|какое|какие|когда|где|кто|что|сколько|скажи)\b")


def _path() -> Path:
    return memory.DATA_DIR / "facts.json"


def _load() -> list[dict]:
    data = memory._read_json(_path(), [])  # noqa: SLF001
    return [f for f in data if isinstance(f, dict) and str(f.get("text", "")).strip()] if isinstance(data, list) else []


def _save(facts: list[dict]) -> None:
    memory._write_json(_path(), facts[-MAX_FACTS:])  # noqa: SLF001


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("ё", "е")).strip()


def _stems(text: str) -> set[str]:
    # Crude Russian stemming: a 5-letter prefix survives most case/number endings.
    words = re.findall(r"\w+", _norm(text))
    return {w[:5] for w in words if len(w) >= 3 and w not in _STOP_WORDS}


def clean_fact(text: str) -> str:
    text = (text or "").strip().strip(" .,!?;:—-«»\"'")
    return text[:1].upper() + text[1:] if text else ""


def add(text: str) -> str:
    fact = clean_fact(text)
    if not fact:
        return "Что именно запомнить, сэр?"
    with memory._lock:  # noqa: SLF001
        facts = _load()
        if any(_norm(f["text"]) == _norm(fact) for f in facts):
            return f"Я это уже помню: {fact}."
        facts.append({"text": fact, "created": datetime.now().isoformat(timespec="seconds")})
        _save(facts)
    return f"Запомнил: {fact}."


def all_facts() -> list[str]:
    return [str(f["text"]) for f in _load()]


def list_text(limit: int = 10) -> str:
    facts = all_facts()
    if not facts:
        return "Пока ничего о вас не знаю. Скажите: «запомни, что …»."
    shown = facts[-limit:]
    more = f" И ещё {len(facts) - limit}." if len(facts) > limit else ""
    return "Вот что я помню: " + "; ".join(shown) + "." + more


def forget(query: str) -> str:
    needle = _stems(query)
    if not needle:
        return "Что именно забыть, сэр?"
    with memory._lock:  # noqa: SLF001
        facts = _load()
        kept = [f for f in facts if not (needle & _stems(f["text"]))]
        removed = len(facts) - len(kept)
        if not removed:
            return "Ничего такого не помню."
        _save(kept)
    return "Забыл." if removed == 1 else f"Забыл {removed} фактов."


def clear() -> str:
    with memory._lock:  # noqa: SLF001
        _save([])
    return "Всё, что знал о вас, стёрто."


def is_personal_question(text: str) -> bool:
    t = _norm(text)
    return bool(_QUESTION.match(t) and _PERSONAL.search(t))


def find(question: str) -> str | None:
    """Best-matching fact for a question, or None if nothing overlaps."""
    q = _stems(question)
    if not q:
        return None
    best, best_score = None, 0
    for fact in all_facts():
        score = len(q & _stems(fact))
        if score > best_score:
            best, best_score = fact, score
    return best


def answer(question: str) -> str | None:
    if not is_personal_question(question):
        return None
    fact = find(question)
    return f"Вы говорили: {fact}." if fact else None


def prompt_context() -> str:
    """Facts block for LLM system prompts."""
    facts = all_facts()[-PROMPT_FACTS:]
    if not facts:
        return ""
    return "Известные факты о пользователе (используй, если уместно):\n- " + "\n- ".join(facts)
