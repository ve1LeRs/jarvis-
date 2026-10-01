"""Optional local LLM (Ollama) for free-form intent routing and follow-ups."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from jarvis import memory

FOLLOWUP_KEY = "llm_followup"
DEFAULT_MODEL = os.getenv("JARVIS_OLLAMA_MODEL", "llama3.2")
OLLAMA_URL = os.getenv("JARVIS_OLLAMA_URL", "http://127.0.0.1:11434")


def available() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _chat(prompt: str, *, system: str = "", timeout: float = 20.0) -> str | None:
    body: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "stream": False,
        "messages": [],
        "options": {"temperature": 0.2},
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/chat",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None
    message = payload.get("message") or {}
    content = message.get("content")
    return str(content).strip() if content else None


_SYSTEM_ROUTE = (
    "Ты роутер команд голосового ассистента JARVIS. "
    "Верни ТОЛЬКО одну короткую команду на русском без кавычек, "
    "которую ассистент уже умеет, например: запусти пабг, открой дискорд, "
    "включи Bohemian Rhapsody в спотифай, что сегодня, напомни в 18:00 чай. "
    "Если это вопрос — верни исходный вопрос. Если непонятно — верни пустую строку."
)


def route_command(text: str) -> str | None:
    """Map free-form utterance to a known-style command via local LLM."""
    text = (text or "").strip()
    if not text or not available():
        return None
    out = _chat(text, system=_SYSTEM_ROUTE, timeout=12.0)
    if not out:
        return None
    # Keep first line, strip markdown
    line = out.splitlines()[0].strip().strip("`\"'")
    if not line or line.lower() in {"неизвестно", "unknown", "none", "null"}:
        return None
    if len(line) > 200:
        line = line[:200]
    return line


def answer(text: str) -> str | None:
    text = (text or "").strip()
    if not text or not available():
        return None
    system = (
        "Отвечай кратко по-русски, 1–3 предложения, как JARVIS. "
        "Без списков и markdown, если не просят."
    )
    # Include short follow-up context
    follow = memory.get_settings().get(FOLLOWUP_KEY) or ""
    prompt = text
    if follow:
        prompt = f"Контекст прошлого ответа: {follow}\nВопрос: {text}"
    out = _chat(prompt, system=system, timeout=25.0)
    if out:
        memory.update_settings(**{FOLLOWUP_KEY: out[:400]})
    return out


def clear_followup() -> None:
    memory.update_settings(**{FOLLOWUP_KEY: ""})


def status_text() -> str:
    if available():
        return f"Локальная модель Ollama доступна ({DEFAULT_MODEL})."
    return (
        "Локальная LLM недоступна. Установите Ollama и модель "
        f"({DEFAULT_MODEL}), либо задайте JARVIS_OLLAMA_URL."
    )


def looks_like_followup(text: str) -> bool:
    t = (text or "").lower().strip()
    return bool(
        re.match(
            r"^(а|и|ну|тогда|ещё|еще|подробнее|продолжи|а\s+что|почему|зачем)\b",
            t,
        )
    )
