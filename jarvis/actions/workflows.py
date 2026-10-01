"""Multi-app presets for work and gaming sessions."""

from __future__ import annotations

from jarvis.actions import chrome_app
from jarvis.actions import cursor_app
from jarvis.actions import discord_app
from jarvis.actions import games
from jarvis.actions import spotify as spotify_act
from jarvis.actions import word_app


def work_mode() -> str:
    """Cursor + Chrome + Word — typical work setup."""
    parts = [
        cursor_app.open_cursor(),
        chrome_app.open_chrome(),
        word_app.open_word(),
    ]
    return "Рабочий режим: " + " ".join(parts)


def coding_mode() -> str:
    parts = [
        cursor_app.open_cursor(),
        chrome_app.open_chrome("https://github.com"),
    ]
    return "Режим кода: " + " ".join(parts)


def chill_mode() -> str:
    parts = [
        spotify_act.open_spotify(),
        discord_app.open_discord(),
        chrome_app.open_chrome("https://www.youtube.com"),
    ]
    return "Чилл-режим: " + " ".join(parts)


def game_mode_cs2() -> str:
    return games.game_mode("cs2", with_discord=True, pause_music=True)


def game_mode_pubg() -> str:
    return games.game_mode("pubg", with_discord=True, pause_music=True)


def stack_status() -> str:
    """Describe the favorite stack Jarvis knows well."""
    return (
        "Ваш стек: Discord, Chrome, Spotify, CS2, PUBG, Cursor и Word. "
        "Могу открывать их, включать игровой/рабочий режим, "
        "ставить треки, мьютить Discord и создавать документы."
    )
