"""Google Chrome helpers beyond basic open/search."""

from __future__ import annotations

import time
from urllib.parse import quote_plus

from jarvis.actions import launch
from jarvis.actions import system as sys_act


def open_chrome(url: str | None = None) -> str:
    return sys_act.open_chrome(url)


def focus_chrome() -> str:
    if launch.focus_window(["chrome", "google chrome"]):
        return "Переключаюсь на Chrome."
    return open_chrome()


def new_tab(url: str | None = None) -> str:
    open_chrome()
    time.sleep(0.5)
    launch.focus_window(["chrome", "google chrome"])
    if launch.send_hotkey("ctrl", "t"):
        if url:
            time.sleep(0.25)
            # Typing URL via clipboard would be nicer; open directly is more reliable.
            return sys_act.open_chrome(url)
        return "Открываю новую вкладку в Chrome."
    if url:
        return sys_act.open_chrome(url)
    return open_chrome()


def close_tab() -> str:
    if not launch.focus_window(["chrome", "google chrome"]):
        open_chrome()
        time.sleep(0.4)
        launch.focus_window(["chrome", "google chrome"])
    if launch.send_hotkey("ctrl", "w"):
        return "Закрываю вкладку Chrome."
    return "Не удалось закрыть вкладку — сфокусируйте Chrome."


def reopen_tab() -> str:
    launch.focus_window(["chrome", "google chrome"])
    if launch.send_hotkey("ctrl", "shift", "t"):
        return "Возвращаю закрытую вкладку."
    return "Не удалось вернуть вкладку."


def refresh() -> str:
    launch.focus_window(["chrome", "google chrome"])
    if launch.send_hotkey("f5"):
        return "Обновляю страницу."
    return "Не удалось обновить страницу."


def incognito(url: str | None = None) -> str:
    chrome = sys_act._find_chrome()  # noqa: SLF001
    target = url or "https://www.google.com"
    if chrome:
        launch.run([chrome, "--incognito", target])
        return "Открываю инкогнито в Chrome."
    return sys_act.open_chrome(target)


def search(query: str) -> str:
    return sys_act.search_web(query)


def open_site(name: str) -> str:
    key = (name or "").lower().strip()
    sites = {
        "youtube": "https://www.youtube.com",
        "ютуб": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "почта": "https://mail.google.com",
        "github": "https://github.com",
        "гитхаб": "https://github.com",
        "переводчик": "https://translate.google.com/?hl=ru",
        "drive": "https://drive.google.com",
        "диск": "https://drive.google.com",
        "chatgpt": "https://chatgpt.com",
        "чатгпт": "https://chatgpt.com",
        "cursor": "https://cursor.com",
        "курсор": "https://cursor.com",
        "discord": "https://discord.com/app",
        "дискорд": "https://discord.com/app",
        "spotify": "https://open.spotify.com",
        "спотифай": "https://open.spotify.com",
    }
    if key in sites:
        return open_chrome(sites[key])
    if key.startswith("http"):
        return open_chrome(key)
    return search(key)


def youtube_search(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    return open_chrome(url)
