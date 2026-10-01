"""OS actions: browser, explorer, apps, system utilities."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from jarvis import config

SYSTEM = platform.system()


def _run(command: list[str] | str, *, shell: bool = False) -> None:
    kwargs: dict = {"shell": shell}
    if SYSTEM == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(command, **kwargs)


def open_url(url: str) -> str:
    webbrowser.open(url)
    return f"Открываю: {url}"


def search_web(query: str) -> str:
    url = config.SEARCH_URL.format(query=quote_plus(query))
    # Prefer Google Chrome if installed.
    chrome = _find_chrome()
    if chrome:
        _run([chrome, url])
    else:
        webbrowser.open(url)
    return f"Ищу в Chrome: {query}"


def _find_chrome() -> str | None:
    if SYSTEM == "Windows":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in candidates:
            if Path(path).exists():
                return path
    elif SYSTEM == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if Path(path).exists():
            return path
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                return found
    return None


def open_chrome(url: str | None = None) -> str:
    chrome = _find_chrome()
    target = url or "https://www.google.com"
    if chrome:
        _run([chrome, target])
        return "Открываю Chrome."
    webbrowser.open(target)
    return "Chrome не найден — открываю браузер по умолчанию."


def _find_steam() -> str | None:
    """Typical Steam install locations on Windows / other OS."""
    if SYSTEM == "Windows":
        candidates = [
            # Most common default install
            r"C:\Program Files (x86)\Steam\steam.exe",
            os.path.expandvars(r"%ProgramFiles(x86)%\Steam\steam.exe"),
            os.path.expandvars(r"%ProgramFiles%\Steam\steam.exe"),
            os.path.expandvars(r"%LocalAppData%\Programs\Steam\steam.exe"),
            os.path.expanduser(r"~\Steam\steam.exe"),
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None
    if SYSTEM == "Darwin":
        path = "/Applications/Steam.app"
        if os.path.isdir(path) or os.path.exists(path):
            return path
    else:
        for name in ("steam", "steam-runtime"):
            found = shutil.which(name)
            if found:
                return found
    return None


def open_steam() -> str:
    steam = _find_steam()
    if steam:
        if SYSTEM == "Darwin" and steam.endswith(".app"):
            _run(["open", steam])
        else:
            _run([steam])
        return "Открываю Steam."
    if SYSTEM == "Windows":
        # Last resort: protocol handler / PATH
        try:
            os.startfile("steam:")  # type: ignore[attr-defined]
            return "Открываю Steam."
        except Exception:
            _run(["cmd", "/c", "start", "", "steam:"])
            return "Пытаюсь открыть Steam."
    return "Steam не найден. Обычный путь: C:\\Program Files (x86)\\Steam\\steam.exe"


def open_explorer(path: str | None = None) -> str:
    target = path or os.path.expanduser("~")
    if SYSTEM == "Windows":
        _run(["explorer", target])
        return "Открываю Проводник."
    if SYSTEM == "Darwin":
        _run(["open", target])
        return "Открываю Finder."
    # Linux file managers
    for fm in ("xdg-open", "nautilus", "dolphin", "thunar", "pcmanfm"):
        if shutil.which(fm):
            _run([fm, target])
            return "Открываю файловый менеджер."
    return "Не удалось открыть проводник."


def open_app(name: str) -> str:
    """Open a common application by friendly Russian/English name."""
    key = name.lower().strip()
    apps_win = {
        "блокнот": "notepad",
        "калькулятор": "calc",
        "кальк": "calc",
        "paint": "mspaint",
        "пейнт": "mspaint",
        "cmd": "cmd",
        "терминал": "wt",
        "powershell": "powershell",
        "параметры": "ms-settings:",
        "настройки": "ms-settings:",
        "диспетчер задач": "taskmgr",
        "задача": "taskmgr",
        "word": "winword",
        "excel": "excel",
        "spotify": "spotify",
        "telegram": "telegram",
        "discord": "discord",
        "vscode": "code",
        "vs code": "code",
        "код": "code",
    }
    apps_cross = {
        "хром": lambda: open_chrome(),
        "chrome": lambda: open_chrome(),
        "браузер": lambda: open_chrome(),
        "steam": lambda: open_steam(),
        "стим": lambda: open_steam(),
        "стиме": lambda: open_steam(),
        "youtube": lambda: open_url("https://www.youtube.com"),
        "ютуб": lambda: open_url("https://www.youtube.com"),
        "ютубе": lambda: open_url("https://www.youtube.com"),
        "почта": lambda: open_url("https://mail.google.com"),
        "gmail": lambda: open_url("https://mail.google.com"),
        "переводчик": lambda: open_url("https://translate.google.com/?hl=ru"),
        "погода": lambda: open_url("https://www.google.com/search?q=погода"),
    }

    if key in apps_cross:
        return apps_cross[key]()

    if SYSTEM == "Windows":
        exe = apps_win.get(key)
        if exe:
            if exe.startswith("ms-"):
                os.startfile(exe)  # type: ignore[attr-defined]
            else:
                try:
                    _run(exe, shell=True)
                except Exception:
                    _run(["cmd", "/c", "start", "", exe])
            return f"Открываю {name}."
        # Try start by name
        _run(["cmd", "/c", "start", "", key])
        return f"Пытаюсь открыть {name}."

    found = shutil.which(key)
    if found:
        _run([found])
        return f"Открываю {name}."
    return f"Не нашёл приложение «{name}»."


def tell_time() -> str:
    now = datetime.now()
    return f"Сейчас {now.strftime('%H:%M')}."


def tell_date() -> str:
    months = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    now = datetime.now()
    return f"Сегодня {now.day} {months[now.month - 1]} {now.year} года."


def open_downloads() -> str:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        downloads = Path.home() / "Загрузки"
    return open_explorer(str(downloads))


def open_desktop() -> str:
    return open_explorer(str(Path.home() / "Desktop"))


def shutdown_pc() -> str:
    if SYSTEM == "Windows":
        _run(["shutdown", "/s", "/t", "60"])
        return "Выключение через 60 секунд. Скажите «джарвис, отмена» чтобы отменить."
    if SYSTEM == "Darwin":
        _run(["osascript", "-e", 'tell app "System Events" to shut down'])
        return "Отправлена команда выключения."
    _run(["shutdown", "-h", "+1"])
    return "Выключение через 1 минуту."


def cancel_shutdown() -> str:
    if SYSTEM == "Windows":
        _run(["shutdown", "/a"])
        return "Выключение отменено."
    _run(["shutdown", "-c"])
    return "Выключение отменено."


def lock_pc() -> str:
    if SYSTEM == "Windows":
        _run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "Блокирую компьютер."
    if SYSTEM == "Darwin":
        _run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "q" using {command down, control down}',
            ]
        )
        return "Блокирую компьютер."
    if shutil.which("loginctl"):
        _run(["loginctl", "lock-session"])
        return "Блокирую сессию."
    return "Не удалось заблокировать."
