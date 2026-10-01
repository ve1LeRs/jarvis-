"""Self-update from GitHub Releases (exe) or git (source checkout)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable

from jarvis.version import BUILD

REPO = os.getenv("JARVIS_UPDATE_REPO", "ve1lers/jarvis-")
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "JARVIS.exe"
TAG_PREFIX = "build-"
CHECK_INTERVAL_SECONDS = 6 * 60 * 60

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_lock = threading.Lock()


def updates_disabled() -> bool:
    return os.getenv("JARVIS_NO_UPDATE", "").strip() not in ("", "0")


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _fetch_latest_release() -> dict:
    req = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "JARVIS-updater"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _release_build(release: dict) -> int:
    tag = str(release.get("tag_name", ""))
    if not tag.startswith(TAG_PREFIX):
        return -1
    try:
        return int(tag[len(TAG_PREFIX):])
    except ValueError:
        return -1


def _asset_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            return asset.get("browser_download_url")
    return None


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-updater"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
        while chunk := resp.read(1 << 16):
            fh.write(chunk)
    tmp.replace(dest)


def _restart_with_new_exe(new_exe: Path) -> None:
    """Swap the running exe via a detached batch script, then exit."""
    current = Path(sys.executable).resolve()
    args = subprocess.list2cmdline(sys.argv[1:])
    script = Path(tempfile.gettempdir()) / "jarvis_update.cmd"
    # The running exe is locked by Windows until this process exits, hence the retry loop.
    script.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        ":wait\r\n"
        f'tasklist /FI "PID eq {os.getpid()}" | find "{os.getpid()}" >nul && '
        "(timeout /t 1 /nobreak >nul & goto wait)\r\n"
        ":swap\r\n"
        f'move /Y "{new_exe}" "{current}" >nul || (timeout /t 1 /nobreak >nul & goto swap)\r\n'
        f'start "" "{current}" {args}\r\n'
        'del "%~f0"\r\n',
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(script)],
        creationflags=_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0),
        close_fds=True,
    )
    os._exit(0)


def _update_exe(on_status: Callable[[str], None]) -> bool:
    release = _fetch_latest_release()
    latest = _release_build(release)
    if latest <= BUILD:
        return False
    url = _asset_url(release)
    if not url:
        return False

    on_status(f"Найдено обновление JARVIS (сборка {latest}). Скачиваю...")
    new_exe = Path(sys.executable).resolve().with_name("JARVIS.new.exe")
    _download(url, new_exe)
    on_status("Обновление скачано. Перезапускаюсь...")
    _restart_with_new_exe(new_exe)
    return True


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        creationflags=_NO_WINDOW,
        check=True,
    )
    return out.stdout.strip()


def _update_source(on_status: Callable[[str], None]) -> bool:
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        return False
    before = _git(root, "rev-parse", "HEAD")
    _git(root, "pull", "--ff-only")
    after = _git(root, "rev-parse", "HEAD")
    if before == after:
        return False

    on_status("Код JARVIS обновлён. Перезапускаюсь...")
    subprocess.Popen([sys.executable, "-m", "jarvis", *sys.argv[1:]], cwd=root, close_fds=True)
    os._exit(0)
    return True


def check_and_update(on_status: Callable[[str], None] = print) -> bool:
    """Install the newest version if there is one. Restarts the process on success."""
    if updates_disabled() or not _lock.acquire(blocking=False):
        return False
    try:
        if _is_frozen():
            return _update_exe(on_status)
        return _update_source(on_status)
    except Exception as exc:  # noqa: BLE001
        print(f"Проверка обновлений не удалась: {exc}")
        return False
    finally:
        _lock.release()


def start_background_updates(on_status: Callable[[str], None] = print) -> None:
    """Check now and then every CHECK_INTERVAL_SECONDS in a daemon thread."""
    if updates_disabled():
        return

    def _loop() -> None:
        stop = threading.Event()
        while True:
            check_and_update(on_status)
            stop.wait(CHECK_INTERVAL_SECONDS)

    threading.Thread(target=_loop, name="jarvis-updater", daemon=True).start()
