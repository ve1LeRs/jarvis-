"""Multi-app presets for work, gaming and day profiles."""

from __future__ import annotations

from jarvis import context
from jarvis import memory
from jarvis.actions import chrome_app
from jarvis.actions import cursor_app
from jarvis.actions import discord_app
from jarvis.actions import games
from jarvis.actions import spotify as spotify_act
from jarvis.actions import word_app


def work_mode() -> str:
    parts = [
        cursor_app.open_cursor(),
        chrome_app.open_chrome(),
        word_app.open_word(),
    ]
    context.set_mode("work", quiet=False, apps=["Cursor", "Chrome", "Word"])
    return "Рабочий режим: " + " ".join(parts)


def coding_mode() -> str:
    parts = [
        cursor_app.open_cursor(),
        chrome_app.open_chrome("https://github.com"),
    ]
    context.set_mode("code", quiet=False, apps=["Cursor", "Chrome"])
    return "Режим кода: " + " ".join(parts)


def chill_mode() -> str:
    parts = [
        spotify_act.open_spotify(),
        discord_app.open_discord(),
        chrome_app.open_chrome("https://www.youtube.com"),
    ]
    context.set_mode("chill", quiet=False, apps=["Spotify", "Discord", "Chrome"])
    return "Чилл-режим: " + " ".join(parts)


def morning_mode() -> str:
    parts = [
        chrome_app.open_chrome("https://mail.google.com"),
        cursor_app.open_cursor(),
        spotify_act.open_spotify(),
    ]
    context.set_mode("work", quiet=False, apps=["Chrome", "Cursor", "Spotify"])
    brief = memory.today_brief()
    return "Доброе утро. " + " ".join(parts) + " " + brief


def evening_mode() -> str:
    parts = [
        discord_app.open_discord(),
        spotify_act.open_spotify(),
    ]
    context.set_mode("chill", quiet=False, apps=["Discord", "Spotify"])
    return "Вечерний режим: " + " ".join(parts) + " Приятного отдыха, сэр."


def game_mode_cs2() -> str:
    return games.game_mode("cs2", with_discord=True, pause_music=True)


def game_mode_pubg() -> str:
    return games.game_mode("pubg", with_discord=True, pause_music=True)


def stack_status() -> str:
    ctx = context.status_text()
    return (
        "Ваш стек: Discord, Chrome, Spotify, CS2, PUBG, Cursor и Word. "
        "Есть макросы, дела, напоминания по времени, чтение экрана/выделения "
        "и подтверждение опасных команд. "
        + ctx
    )
