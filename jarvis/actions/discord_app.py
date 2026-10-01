"""Discord helpers: launch, focus, mute/deafen, voice join via Quick Switcher."""

from __future__ import annotations

import time
from urllib.parse import quote

from jarvis import memory
from jarvis.actions import launch

VOICE_CHANNEL_KEY = "discord_voice_channel"


def _find_discord() -> str | None:
    try:
        from jarvis import paths

        cached = paths.get_path("discord")
        if cached:
            return cached
    except Exception:
        pass
    return launch.which_or_path(
        "Discord",
        [
            r"%LOCALAPPDATA%\Discord\Update.exe",
            r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
            r"%LOCALAPPDATA%\DiscordCanary\Update.exe",
        ],
    )


def open_discord() -> str:
    path = _find_discord()
    if path and path.lower().endswith("update.exe"):
        launch.run([path, "--processStart", "Discord.exe"])
        launch.focus_window(["discord"])
        return "Открываю Discord."
    if path:
        launch.run([path])
        launch.focus_window(["discord"])
        return "Открываю Discord."
    if launch.open_uri("discord://"):
        return "Открываю Discord."
    if launch.open_uri("https://discord.com/app"):
        return "Приложение не найдено — открываю Discord в браузере."
    return "Не удалось открыть Discord."


def focus_discord() -> str:
    if launch.focus_window(["discord"]):
        return "Переключаюсь на Discord."
    return open_discord()


def _with_focus_hotkey(*keys: str, action: str) -> str:
    open_discord()
    time.sleep(0.8)
    launch.focus_window(["discord"])
    time.sleep(0.2)
    if launch.send_hotkey(*keys):
        return action
    return f"{action} (если не сработало — сфокусируйте окно Discord)."


def toggle_mute() -> str:
    return _with_focus_hotkey("ctrl", "shift", "m", action="Переключаю микрофон в Discord.")


def toggle_deafen() -> str:
    return _with_focus_hotkey("ctrl", "shift", "d", action="Переключаю деф в Discord.")


def set_mute(muted: bool) -> str:
    """Best-effort set mute state by toggling once (no state read)."""
    # Store desired state for game scenario restore.
    memory.update_settings(discord_want_mute=bool(muted))
    return toggle_mute()


def set_deafen(deafened: bool) -> str:
    memory.update_settings(discord_want_deafen=bool(deafened))
    return toggle_deafen()


def open_activity() -> str:
    open_discord()
    if launch.open_uri("https://discord.com/channels/@me"):
        return "Открываю личные сообщения Discord."
    return "Открыл Discord."


def join_invite(code_or_url: str) -> str:
    text = (code_or_url or "").strip()
    if not text:
        return open_discord()
    if text.startswith("http"):
        launch.open_uri(text)
        return "Открываю приглашение Discord."
    code = text.replace("discord.gg/", "").strip("/")
    launch.open_uri(f"https://discord.gg/{quote(code)}")
    return f"Открываю инвайт Discord: {code}."


def remember_voice_channel(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "Назовите голосовой канал."
    memory.update_settings(**{VOICE_CHANNEL_KEY: name})
    return f"Запомнил голосовой канал Discord: {name}."


def join_voice_channel(name: str | None = None) -> str:
    """Join a voice channel via Discord Quick Switcher (Ctrl+K) + typing + Enter.

    Relies on Discord desktop focus; works without UI Automation libraries.
    """
    channel = (name or "").strip() or str(memory.get_settings().get(VOICE_CHANNEL_KEY) or "")
    if not channel:
        return (
            "Назовите канал: «зайди в войс общий» или сначала "
            "«запомни войс канал общий»."
        )

    open_discord()
    time.sleep(1.0)
    launch.focus_window(["discord"])
    time.sleep(0.3)
    # Quick Switcher
    if not launch.send_hotkey("ctrl", "k"):
        return (
            f"Не смог открыть быстрый поиск Discord. Откройте канал «{channel}» вручную."
        )
    time.sleep(0.45)
    if not _type_text(channel):
        return (
            f"Открыл поиск Discord — введите «{channel}» и Enter, "
            "если автонабор недоступен."
        )
    time.sleep(0.35)
    launch.send_hotkey("enter")
    return f"Подключаюсь к голосовому каналу «{channel}» в Discord."


def _type_text(text: str) -> bool:
    """Type unicode text on Windows via clipboard paste (reliable for RU)."""
    if launch.SYSTEM != "Windows":
        return False
    try:
        import ctypes

        # Put text on clipboard via Tk if available, else PowerShell
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
        except Exception:
            # fallback: skip typing
            return False
        # Ctrl+V
        return launch.send_hotkey("ctrl", "v")
    except Exception:
        return False
