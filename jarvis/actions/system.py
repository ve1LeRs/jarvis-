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


def _run_capture(command: list[str] | str, *, shell: bool = False) -> str:
    kwargs: dict = {"shell": shell, "capture_output": True, "text": True}
    if SYSTEM == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(command, **kwargs, check=False)
        return (completed.stdout or "").strip()
    except Exception:
        return ""


def open_url(url: str) -> str:
    webbrowser.open(url)
    return f"Открываю: {url}"


def search_web(query: str) -> str:
    url = config.SEARCH_URL.format(query=quote_plus(query))
    chrome = _find_chrome()
    if chrome:
        _run([chrome, url])
    else:
        webbrowser.open(url)
    return f"Ищу в Chrome: {query}"


def search_youtube(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    chrome = _find_chrome()
    if chrome:
        _run([chrome, url])
    else:
        webbrowser.open(url)
    return f"Ищу на YouTube: {query}"


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


def open_explorer(path: str | None = None) -> str:
    target = path or os.path.expanduser("~")
    if SYSTEM == "Windows":
        _run(["explorer", target])
        return "Открываю Проводник."
    if SYSTEM == "Darwin":
        _run(["open", target])
        return "Открываю Finder."
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
        "спотифай": "spotify",
        "telegram": "telegram",
        "discord": "discord",
        "vscode": "code",
        "vs code": "code",
        "код": "code",
        "edge": "msedge",
        "эдж": "msedge",
    }
    apps_cross = {
        "хром": lambda: open_chrome(),
        "chrome": lambda: open_chrome(),
        "браузер": lambda: open_chrome(),
        "youtube": lambda: open_url("https://www.youtube.com"),
        "ютуб": lambda: open_url("https://www.youtube.com"),
        "ютубе": lambda: open_url("https://www.youtube.com"),
        "почта": lambda: open_url("https://mail.google.com"),
        "gmail": lambda: open_url("https://mail.google.com"),
        "переводчик": lambda: open_url("https://translate.google.com/?hl=ru"),
        "погода": lambda: open_weather(),
        "карты": lambda: open_url("https://maps.google.com"),
        "новости": lambda: open_url("https://news.google.com/?hl=ru"),
        "github": lambda: open_url("https://github.com"),
        "гитхаб": lambda: open_url("https://github.com"),
    }

    if key in apps_cross:
        return apps_cross[key]()

    if key in {"spotify", "спотифай"}:
        from jarvis.actions import spotify as spotify_act

        return spotify_act.open_spotify()

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
    weekdays = (
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )
    now = datetime.now()
    return (
        f"Сегодня {weekdays[now.weekday()]}, "
        f"{now.day} {months[now.month - 1]} {now.year} года."
    )


def open_downloads() -> str:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        downloads = Path.home() / "Загрузки"
    return open_explorer(str(downloads))


def open_desktop() -> str:
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home() / "Рабочий стол"
    return open_explorer(str(desktop))


def open_documents() -> str:
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home() / "Документы"
    return open_explorer(str(docs))


def open_pictures() -> str:
    pics = Path.home() / "Pictures"
    if not pics.exists():
        pics = Path.home() / "Изображения"
    return open_explorer(str(pics))


def open_music() -> str:
    music = Path.home() / "Music"
    if not music.exists():
        music = Path.home() / "Музыка"
    return open_explorer(str(music))


def open_weather(city: str | None = None) -> str:
    query = f"погода {city}".strip() if city else "погода"
    return search_web(query)


def shutdown_pc() -> str:
    if SYSTEM == "Windows":
        _run(["shutdown", "/s", "/t", "60"])
        return "Выключение через 60 секунд. Скажите «джарвис, отмена» чтобы отменить."
    if SYSTEM == "Darwin":
        _run(["osascript", "-e", 'tell app "System Events" to shut down'])
        return "Отправлена команда выключения."
    _run(["shutdown", "-h", "+1"])
    return "Выключение через 1 минуту."


def restart_pc() -> str:
    if SYSTEM == "Windows":
        _run(["shutdown", "/r", "/t", "60"])
        return "Перезагрузка через 60 секунд. Скажите «отмена», чтобы отменить."
    if SYSTEM == "Darwin":
        _run(["osascript", "-e", 'tell app "System Events" to restart'])
        return "Отправлена команда перезагрузки."
    _run(["shutdown", "-r", "+1"])
    return "Перезагрузка через 1 минуту."


def sleep_pc() -> str:
    if SYSTEM == "Windows":
        _run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return "Перевожу компьютер в сон."
    if SYSTEM == "Darwin":
        _run(["pmset", "sleepnow"])
        return "Перевожу компьютер в сон."
    if shutil.which("systemctl"):
        _run(["systemctl", "suspend"])
        return "Перевожу компьютер в сон."
    return "Не удалось усыпить компьютер."


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


def _press_vk(vk_code: int, times: int = 1) -> None:
    """Simulate a Windows virtual-key press (volume/media)."""
    if SYSTEM != "Windows":
        return
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    KEYEVENTF_KEYUP = 0x0002
    for _ in range(max(1, times)):
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def volume_up(steps: int = 4) -> str:
    if SYSTEM == "Windows":
        _press_vk(0xAF, steps)  # VK_VOLUME_UP
        return "Громкость выше."
    if SYSTEM == "Darwin":
        _run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 10)"])
        return "Громкость выше."
    if shutil.which("amixer"):
        _run(["amixer", "set", "Master", "5%+"])
        return "Громкость выше."
    return "Не удалось изменить громкость."


def volume_down(steps: int = 4) -> str:
    if SYSTEM == "Windows":
        _press_vk(0xAE, steps)  # VK_VOLUME_DOWN
        return "Громкость ниже."
    if SYSTEM == "Darwin":
        _run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 10)"])
        return "Громкость ниже."
    if shutil.which("amixer"):
        _run(["amixer", "set", "Master", "5%-"])
        return "Громкость ниже."
    return "Не удалось изменить громкость."


def volume_mute() -> str:
    if SYSTEM == "Windows":
        _press_vk(0xAD)  # VK_VOLUME_MUTE
        return "Переключаю звук."
    if SYSTEM == "Darwin":
        _run(["osascript", "-e", "set volume output muted true"])
        return "Звук выключен."
    if shutil.which("amixer"):
        _run(["amixer", "set", "Master", "toggle"])
        return "Переключаю звук."
    return "Не удалось переключить звук."


def media_play_pause() -> str:
    if SYSTEM == "Windows":
        _press_vk(0xB3)
        return "Плей или пауза."
    return "Управление медиа доступно в Windows."


def media_next() -> str:
    if SYSTEM == "Windows":
        _press_vk(0xB0)
        return "Следующий трек."
    return "Управление медиа доступно в Windows."


def media_prev() -> str:
    if SYSTEM == "Windows":
        _press_vk(0xB1)
        return "Предыдущий трек."
    return "Управление медиа доступно в Windows."


def take_screenshot() -> str:
    pictures = Path.home() / "Pictures"
    if not pictures.exists():
        pictures = Path.home() / "Изображения"
    pictures.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = pictures / f"JARVIS_{stamp}.png"

    if SYSTEM == "Windows":
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab()
            image.save(str(target))
            return f"Скриншот сохранён: {target}"
        except Exception:
            # Fallback: Win+PrintScreen via PowerShell is unreliable; try snipping tool folder.
            pass

    if SYSTEM == "Darwin":
        _run(["screencapture", "-x", str(target)])
        return f"Скриншот сохранён: {target}"

    for tool in ("gnome-screenshot", "scrot", "import"):
        if shutil.which(tool):
            if tool == "import":
                _run([tool, "-window", "root", str(target)])
            elif tool == "gnome-screenshot":
                _run([tool, "-f", str(target)])
            else:
                _run([tool, str(target)])
            return f"Скриншот сохранён: {target}"
    return "Не удалось сделать скриншот."


def read_clipboard() -> str:
    try:
        if SYSTEM == "Windows":
            out = _run_capture(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Clipboard",
                ]
            )
            if out:
                preview = out if len(out) <= 160 else out[:157] + "..."
                return f"В буфере: {preview}"
            return "Буфер обмена пуст."
        if SYSTEM == "Darwin":
            out = _run_capture(["pbpaste"])
            if out:
                preview = out if len(out) <= 160 else out[:157] + "..."
                return f"В буфере: {preview}"
            return "Буфер обмена пуст."
        if shutil.which("xclip"):
            out = _run_capture(["xclip", "-selection", "clipboard", "-o"])
            if out:
                preview = out if len(out) <= 160 else out[:157] + "..."
                return f"В буфере: {preview}"
    except Exception:
        pass
    return "Не удалось прочитать буфер обмена."


def empty_recycle_bin() -> str:
    if SYSTEM == "Windows":
        _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Clear-RecycleBin -Force -ErrorAction SilentlyContinue",
            ]
        )
        return "Очищаю корзину."
    trash = Path.home() / ".local/share/Trash/files"
    if trash.exists():
        for item in trash.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                continue
        return "Очищаю корзину."
    return "Корзина недоступна."


def system_status() -> str:
    bits = [f"Система: {SYSTEM}", f"Время: {datetime.now().strftime('%H:%M')}"]
    try:
        if SYSTEM == "Windows":
            battery = _run_capture(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Battery).EstimatedChargeRemaining",
                ]
            )
            if battery.isdigit():
                bits.append(f"Заряд батареи: {battery}%")
        elif Path("/sys/class/power_supply/BAT0/capacity").exists():
            capacity = Path("/sys/class/power_supply/BAT0/capacity").read_text().strip()
            bits.append(f"Заряд батареи: {capacity}%")
    except Exception:
        pass
    try:
        if hasattr(os, "getloadavg"):
            load = os.getloadavg()[0]
            bits.append(f"Нагрузка: {load:.2f}")
    except OSError:
        pass
    return ". ".join(bits) + "."
