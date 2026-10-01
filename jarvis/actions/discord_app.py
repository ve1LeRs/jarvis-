"""Discord helpers: launch, focus, mute/deafen hotkeys, quick links."""

from __future__ import annotations

import time
from urllib.parse import quote

from jarvis.actions import launch


def _find_discord() -> str | None:
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
