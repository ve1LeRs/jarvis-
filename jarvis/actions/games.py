"""Steam games: Counter-Strike 2 and PUBG."""

from __future__ import annotations

import os
import time

from jarvis import context
from jarvis.actions import discord_app
from jarvis.actions import launch

# Official Steam app IDs
CS2_APP_ID = os.getenv("JARVIS_CS2_APP_ID", "730")
PUBG_APP_ID = os.getenv("JARVIS_PUBG_APP_ID", "578080")


def _launch_steam_game(app_id: str, title: str, window_hints: list[str]) -> str:
    steam = launch.find_steam_exe()
    if steam:
        launch.run([steam, "-applaunch", str(app_id)])
    elif not launch.steam_run(app_id):
        return f"Не удалось запустить {title}. Проверьте, что Steam установлен."
    time.sleep(1.0)
    launch.focus_window(window_hints)
    return f"Запускаю {title}."


def launch_cs2() -> str:
    msg = _launch_steam_game(
        CS2_APP_ID,
        "Counter-Strike 2",
        ["counter-strike", "cs2", "cs 2"],
    )
    context.set_mode("game", game="cs2", quiet=True, apps=["Steam", "CS2"])
    return msg


def launch_pubg() -> str:
    msg = _launch_steam_game(
        PUBG_APP_ID,
        "PUBG",
        ["pubg", "battlegrounds"],
    )
    context.set_mode("game", game="pubg", quiet=True, apps=["Steam", "PUBG"])
    return msg


def _pause_spotify_soft() -> None:
    try:
        from jarvis.actions import system as sys_act

        sys_act.media_play_pause()
    except Exception:
        pass


def game_mode(
    game: str,
    *,
    with_discord: bool = True,
    pause_music: bool = True,
    with_friends: bool = False,
) -> str:
    """Prepare a typical gaming session."""
    key = (game or "").lower().strip()
    parts: list[str] = []

    if with_discord:
        parts.append(discord_app.open_discord())
        time.sleep(0.6)
        if with_friends:
            parts.append(discord_app.open_activity())
            parts.append("Откройте голосовой канал с друзьями в Discord.")

    if pause_music:
        _pause_spotify_soft()
        parts.append("Музыку поставил на паузу.")

    if key in {"кс", "кс2", "cs", "cs2", "counter-strike", "counter strike", "контра"}:
        parts.append(launch_cs2())
        context.set_mode(
            "game",
            game="cs2",
            quiet=True,
            apps=["Discord", "CS2"] if with_discord else ["CS2"],
        )
        prefix = "Режим с друзьями: " if with_friends else ""
        return prefix + " ".join(parts)
    if key in {"пабг", "pubg", "пабджи", "battlegrounds", "пубг"}:
        parts.append(launch_pubg())
        context.set_mode(
            "game",
            game="pubg",
            quiet=True,
            apps=["Discord", "PUBG"] if with_discord else ["PUBG"],
        )
        prefix = "Режим с друзьями: " if with_friends else ""
        return prefix + " ".join(parts)
    return "Скажите: игровой режим кс или игровой режим пабг."


def friends_mode(game: str) -> str:
    return game_mode(game, with_discord=True, pause_music=True, with_friends=True)
