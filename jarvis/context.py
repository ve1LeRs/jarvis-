"""Runtime context: current mode and speech style."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

_lock = threading.RLock()


@dataclass
class SessionContext:
    mode: str = "idle"  # idle | work | code | chill | game | focus
    game: str = ""
    quiet: bool = False  # shorter answers (e.g. while gaming)
    last_apps: list[str] = field(default_factory=list)
    updated_at: str = ""


_ctx = SessionContext()


def get() -> SessionContext:
    with _lock:
        return SessionContext(
            mode=_ctx.mode,
            game=_ctx.game,
            quiet=_ctx.quiet,
            last_apps=list(_ctx.last_apps),
            updated_at=_ctx.updated_at,
        )


def set_mode(mode: str, *, game: str = "", quiet: bool | None = None, apps: list[str] | None = None) -> None:
    with _lock:
        _ctx.mode = mode
        _ctx.game = game
        if quiet is not None:
            _ctx.quiet = quiet
        elif mode == "game":
            _ctx.quiet = True
        elif mode in {"work", "code", "chill", "idle"}:
            _ctx.quiet = False
        if apps is not None:
            _ctx.last_apps = list(apps)
        _ctx.updated_at = datetime.now().isoformat(timespec="seconds")


def status_text() -> str:
    ctx = get()
    parts = [f"Режим: {ctx.mode}"]
    if ctx.game:
        parts.append(f"игра: {ctx.game}")
    if ctx.quiet:
        parts.append("тихие ответы")
    if ctx.last_apps:
        parts.append("приложения: " + ", ".join(ctx.last_apps))
    return ". ".join(parts) + "."


def adapt_speech(text: str) -> str:
    """Shorten verbose answers while in game/quiet mode."""
    ctx = get()
    if not ctx.quiet:
        return text
    text = (text or "").strip()
    if len(text) <= 160:
        return text
    # Keep first sentence-ish chunk.
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if 40 <= idx <= 180:
            return text[: idx + 1]
    return text[:157].rstrip() + "…"
