"""Steam games: Counter-Strike 2 and PUBG + match/session scenarios."""

from __future__ import annotations

import os
import time

from jarvis import context
from jarvis import memory
from jarvis import proactive
from jarvis.actions import discord_app
from jarvis.actions import launch

# Official Steam app IDs
CS2_APP_ID = os.getenv("JARVIS_CS2_APP_ID", "730")
PUBG_APP_ID = os.getenv("JARVIS_PUBG_APP_ID", "578080")

SESSION_KEY = "game_session"


def _launch_steam_game(app_id: str, title: str, window_hints: list[str]) -> str:
    steam = None
    try:
        from jarvis import paths

        steam = paths.get_path("steam")
    except Exception:
        steam = None
    steam = steam or launch.find_steam_exe()
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
    proactive.note_game_started()
    return msg


def launch_pubg() -> str:
    msg = _launch_steam_game(
        PUBG_APP_ID,
        "PUBG",
        ["pubg", "battlegrounds"],
    )
    context.set_mode("game", game="pubg", quiet=True, apps=["Steam", "PUBG"])
    proactive.note_game_started()
    return msg


def _pause_spotify_soft() -> None:
    try:
        from jarvis.actions import system as sys_act

        sys_act.media_play_pause()
    except Exception:
        pass


def _save_session(**kwargs) -> None:
    session = dict(memory.get_settings().get(SESSION_KEY) or {})
    session.update(kwargs)
    memory.update_settings(**{SESSION_KEY: session})


def game_mode(
    game: str,
    *,
    with_discord: bool = True,
    pause_music: bool = True,
    with_friends: bool = False,
    match: bool = False,
) -> str:
    """Prepare a typical gaming session."""
    key = (game or "").lower().strip()
    parts: list[str] = []
    paused_music = False
    deafened = False

    if with_discord:
        parts.append(discord_app.open_discord())
        time.sleep(0.6)
        if with_friends:
            parts.append(discord_app.open_activity())
            # Try remembered voice channel
            voice = str(memory.get_settings().get(discord_app.VOICE_CHANNEL_KEY) or "")
            if voice:
                parts.append(discord_app.join_voice_channel(voice))
            else:
                parts.append("Откройте голосовой канал с друзьями в Discord.")

    if pause_music:
        _pause_spotify_soft()
        paused_music = True
        parts.append("Музыку поставил на паузу.")

    if match and with_discord:
        parts.append(discord_app.toggle_deafen())
        deafened = True
        parts.append("Деф на время матча.")

    game_name = ""
    if key in {"кс", "кс2", "cs", "cs2", "counter-strike", "counter strike", "контра"}:
        parts.append(launch_cs2())
        game_name = "cs2"
        apps = ["Discord", "CS2"] if with_discord else ["CS2"]
        context.set_mode("game", game=game_name, quiet=True, apps=apps)
        _save_session(
            game=game_name,
            paused_music=paused_music,
            deafened=deafened,
            with_discord=with_discord,
            match=match,
        )
        proactive.note_game_started()
        prefix = "Матч: " if match else ("Режим с друзьями: " if with_friends else "")
        return prefix + " ".join(parts)
    if key in {"пабг", "pubg", "пабджи", "battlegrounds", "пубг"}:
        parts.append(launch_pubg())
        game_name = "pubg"
        apps = ["Discord", "PUBG"] if with_discord else ["PUBG"]
        context.set_mode("game", game=game_name, quiet=True, apps=apps)
        _save_session(
            game=game_name,
            paused_music=paused_music,
            deafened=deafened,
            with_discord=with_discord,
            match=match,
        )
        proactive.note_game_started()
        prefix = "Матч: " if match else ("Режим с друзьями: " if with_friends else "")
        return prefix + " ".join(parts)
    return "Скажите: игровой режим кс или игровой режим пабг."


def friends_mode(game: str) -> str:
    return game_mode(game, with_discord=True, pause_music=True, with_friends=True)


def match_mode(game: str) -> str:
    """Match focus: pause Spotify, Discord deafen, launch game, quiet speech."""
    return game_mode(
        game,
        with_discord=True,
        pause_music=True,
        with_friends=False,
        match=True,
    )


def exit_game_mode() -> str:
    """Restore music / undeafen after a session."""
    session = dict(memory.get_settings().get(SESSION_KEY) or {})
    parts: list[str] = ["Выхожу из игрового режима."]
    if session.get("deafened"):
        parts.append(discord_app.toggle_deafen())
    if session.get("paused_music"):
        _pause_spotify_soft()
        parts.append("Музыку вернул.")
    context.set_mode("idle", quiet=False, apps=[])
    proactive.note_game_ended()
    _save_session(game="", paused_music=False, deafened=False, match=False)
    return " ".join(parts)
