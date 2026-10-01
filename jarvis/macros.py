"""User-defined voice macros: custom phrase → command."""

from __future__ import annotations

import re

from jarvis import memory

MACROS_FILE = memory.DATA_DIR / "macros.json"


def _load() -> dict[str, str]:
    data = memory._read_json(MACROS_FILE, {})  # noqa: SLF001
    if not isinstance(data, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()}


def _save(data: dict[str, str]) -> None:
    memory._write_json(MACROS_FILE, data)  # noqa: SLF001


def normalize_phrase(phrase: str) -> str:
    text = (phrase or "").lower().replace("ё", "е").strip()
    text = re.sub(r"[^\w\s\-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def add_macro(phrase: str, command: str) -> str:
    key = normalize_phrase(phrase)
    cmd = (command or "").strip()
    if not key or not cmd:
        return "Нужны фраза и команда. Пример: когда говорю погнали — запускай пабг."
    data = _load()
    data[key] = cmd
    _save(data)
    return f"Запомнил: «{key}» → «{cmd}»."


def remove_macro(phrase: str) -> str:
    key = normalize_phrase(phrase)
    data = _load()
    if key not in data:
        return "Такой макрос не найден."
    data.pop(key, None)
    _save(data)
    return f"Макрос «{key}» удалён."


def list_macros() -> str:
    data = _load()
    if not data:
        return "Макросов пока нет. Скажите: когда говорю погнали — запускай пабг."
    parts = [f"«{k}» → «{v}»" for k, v in data.items()]
    return "Макросы: " + "; ".join(parts)


def resolve(command: str) -> str | None:
    """If command matches a macro phrase, return the mapped command."""
    key = normalize_phrase(command)
    if not key:
        return None
    data = _load()
    return data.get(key)
