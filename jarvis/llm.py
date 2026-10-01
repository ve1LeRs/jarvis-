"""Optional local LLM (Ollama) for free-form intent, follow-ups, and vision."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from jarvis import memory

FOLLOWUP_KEY = "llm_followup"
DEFAULT_MODEL = os.getenv("JARVIS_OLLAMA_MODEL", "llama3.2")
VISION_MODEL = os.getenv("JARVIS_VISION_MODEL", "llava")
OLLAMA_URL = os.getenv("JARVIS_OLLAMA_URL", "http://127.0.0.1:11434")


def available() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            payload = json.loads(resp.read().decode())
    except Exception:
        return []
    names = []
    for item in payload.get("models") or []:
        name = str(item.get("name") or "")
        if name:
            names.append(name)
    return names


def vision_available() -> bool:
    if not available():
        return False
    names = [n.lower() for n in list_models()]
    target = VISION_MODEL.lower()
    if any(target == n or n.startswith(target + ":") or target in n for n in names):
        return True
    # Common vision model families already pulled
    return any(
        any(key in n for key in ("llava", "moondream", "vision", "minicpm-v", "bakllava"))
        for n in names
    )


def _resolve_vision_model() -> str:
    names = list_models()
    lower_map = {n.lower(): n for n in names}
    target = VISION_MODEL.lower()
    for n_lower, n in lower_map.items():
        if n_lower == target or n_lower.startswith(target + ":"):
            return n
    for key in ("llava", "moondream", "llama3.2-vision", "minicpm-v", "bakllava"):
        for n_lower, n in lower_map.items():
            if key in n_lower:
                return n
    return VISION_MODEL


def _chat(
    prompt: str,
    *,
    system: str = "",
    timeout: float = 20.0,
    model: str | None = None,
    images_b64: list[str] | None = None,
) -> str | None:
    body: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "stream": False,
        "messages": [],
        "options": {"temperature": 0.2},
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    user_msg: dict[str, Any] = {"role": "user", "content": prompt}
    if images_b64:
        user_msg["images"] = images_b64
    body["messages"].append(user_msg)
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


def _image_to_b64(path: Path, *, max_side: int = 1280) -> str | None:
    """Encode image as JPEG base64, optionally downscaling via Pillow."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(path)
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return base64.b64encode(raw).decode("ascii")


def describe_image(path: str | Path, question: str | None = None) -> str | None:
    """Ask a vision model what is on the image / answer a question about it."""
    path = Path(path)
    if not path.exists() or not vision_available():
        return None
    b64 = _image_to_b64(path)
    if not b64:
        return None
    prompt = (question or "").strip() or (
        "Опиши экран кратко по-русски: какое приложение открыто, "
        "главные элементы интерфейса и что сейчас важно пользователю. "
        "1–4 предложения, без markdown."
    )
    system = (
        "Ты зрительный модуль JARVIS. Отвечай по-русски, кратко и по делу. "
        "Если видишь кнопки/меню — назови их. Не выдумывай невидимое."
    )
    out = _chat(
        prompt,
        system=system,
        timeout=45.0,
        model=_resolve_vision_model(),
        images_b64=[b64],
    )
    if out:
        memory.update_settings(**{FOLLOWUP_KEY: out[:400]})
    return out


def find_on_image(path: str | Path, target: str) -> str | None:
    """Ask vision where a UI element is and whether it looks clickable."""
    target = (target or "").strip()
    if not target:
        return None
    question = (
        f"Найди на скриншоте элемент «{target}». "
        "Скажи, виден ли он, в какой части экрана (лево/центр/право, верх/низ) "
        "и как он подписан. Если не виден — скажи прямо. Кратко по-русски."
    )
    return describe_image(path, question)


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
    if not available():
        return (
            "Локальная LLM недоступна. Установите Ollama и модель "
            f"({DEFAULT_MODEL}), либо задайте JARVIS_OLLAMA_URL."
        )
    vision = f"vision={_resolve_vision_model()}" if vision_available() else "vision нет (ollama pull llava)"
    return f"Ollama доступна ({DEFAULT_MODEL}; {vision})."


def looks_like_followup(text: str) -> bool:
    t = (text or "").lower().strip()
    return bool(
        re.match(
            r"^(а|и|ну|тогда|ещё|еще|подробнее|продолжи|а\s+что|почему|зачем)\b",
            t,
        )
    )
