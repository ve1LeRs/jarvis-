"""Self-update: JARVIS.exe from GitHub Releases, source checkouts via git."""

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

REPO = os.getenv("JARVIS_UPDATE_REPO", "ve1LeRs/jarvis-")
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "JARVIS.exe"
TAG_PREFIX = "build-"
CHECK_INTERVAL_SECONDS = 6 * 60 * 60

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_lock = threading.Lock()


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def updates_disabled() -> bool:
    return os.getenv("JARVIS_NO_UPDATE", "").strip() not in ("", "0")


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# --- JARVIS.exe: GitHub Releases ---------------------------------------------


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


def _clean_child_env() -> dict[str, str]:
    """Environment for launching another PyInstaller exe as an independent app.

    The onefile bootloader exports _PYI_*/_MEIPASS2 and runtime hooks point TCL/TK
    paths into our temp unpack dir; a child that inherits them reuses a folder that
    disappears as soon as we exit.
    """
    meipass = getattr(sys, "_MEIPASS", "")
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith("_PYI_") or key == "_MEIPASS2":
            continue
        if meipass and meipass in value:
            if key.upper() != "PATH":
                continue
            value = os.pathsep.join(p for p in value.split(os.pathsep) if meipass not in p)
        env[key] = value
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _old_exe_path(current: Path) -> Path:
    old = current.with_name("JARVIS.old.exe")
    try:
        old.unlink(missing_ok=True)
        return old
    except OSError:
        # A previous old copy is still running or locked — pick a fresh name.
        return current.with_name(f"JARVIS.old-{os.getpid()}.exe")


def cleanup_old_exes() -> None:
    """Delete leftovers from previous swaps (the old exe may still be exiting)."""
    if not _is_frozen():
        return
    folder = Path(sys.executable).resolve().parent

    def _run() -> None:
        for _ in range(10):
            leftovers = [
                *folder.glob("JARVIS.old*.exe"),
                folder / "JARVIS.new.exe.part",
                # Helper script of builds <= 6, which swapped files via cmd.exe.
                Path(tempfile.gettempdir()) / "jarvis_update.cmd",
            ]
            remaining = False
            for path in leftovers:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    remaining = True
            if not remaining:
                return
            threading.Event().wait(3)

    threading.Thread(target=_run, name="jarvis-cleanup", daemon=True).start()


def _restart_with_new_exe(new_exe: Path) -> None:
    """Swap exe files and start the new build, then exit.

    Windows refuses to overwrite or delete a running exe but allows renaming it,
    so no helper script has to wait for this process to die.
    """
    current = Path(sys.executable).resolve()
    old = _old_exe_path(current)
    current.rename(old)
    try:
        new_exe.rename(current)
    except OSError:
        old.rename(current)
        raise
    subprocess.Popen(
        [str(current), *sys.argv[1:]],
        cwd=str(current.parent),
        env=_clean_child_env(),
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
    )
    os._exit(0)


def _update_exe(on_status: Callable[[str], None]) -> bool:
    """Raises on network errors; returns False when already up to date."""
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


# --- Source checkout: git ----------------------------------------------------


def _run(cmd: list[str], *, cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )
    except OSError as exc:
        return 1, str(exc)
    out = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode, out


def is_git_checkout(root: Path | None = None) -> bool:
    root = root or project_root()
    return (root / ".git").exists()


def current_branch(root: Path | None = None) -> str:
    root = root or project_root()
    code, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    return out.strip() if code == 0 else ""


def _head(root: Path) -> str:
    code, out = _run(["git", "rev-parse", "HEAD"], cwd=root)
    return out if code == 0 else ""


def _update_source(on_status: Callable[[str], None]) -> bool:
    """Background variant: quiet ff-only pull of the current branch, restart if changed."""
    root = project_root()
    if not is_git_checkout(root):
        return False
    before = _head(root)
    code, _ = _run(["git", "pull", "--ff-only"], cwd=root)
    if code != 0 or _head(root) == before:
        return False

    on_status("Код JARVIS обновлён. Перезапускаюсь...")
    subprocess.Popen([sys.executable, "-m", "jarvis", *sys.argv[1:]], cwd=root, close_fds=True)
    os._exit(0)
    return True


def update_from_git(
    *,
    branch: str | None = None,
    install_deps: bool = True,
) -> str:
    """Manual update ("обнови джарвис" / --update): exe from Releases, source via git + pip."""
    root = project_root()
    if getattr(sys, "frozen", False):
        try:
            _update_exe(print)
        except Exception as exc:  # noqa: BLE001
            return f"Не удалось проверить обновления: {exc}"
        return f"У вас последняя версия JARVIS (сборка {BUILD})."
    if not is_git_checkout(root):
        return (
            "Это не git-клон. Один раз сделайте:\n"
            "  git clone https://github.com/ve1LeRs/jarvis-.git\n"
            "дальше обновляйтесь через update.bat — скачивать архив заново не нужно."
        )

    code, _ = _run(["git", "--version"], cwd=root)
    if code != 0:
        return "Git не найден. Установите Git for Windows: https://git-scm.com/download/win"

    parts: list[str] = []
    target = (branch or os.getenv("JARVIS_UPDATE_BRANCH") or "").strip()
    if not target:
        target = current_branch(root) or "main"

    code, out = _run(["git", "fetch", "--prune", "origin"], cwd=root)
    if code != 0:
        return f"Не удалось связаться с origin.\n{out}"

    code, _ = _run(["git", "rev-parse", "--verify", f"origin/{target}"], cwd=root)
    if code == 0:
        code, out = _run(["git", "pull", "--ff-only", "origin", target], cwd=root)
        if code != 0:
            _run(["git", "checkout", target], cwd=root)
            code, out = _run(["git", "pull", "--ff-only", "origin", target], cwd=root)
            if code != 0:
                return (
                    f"Не удалось обновить ветку {target} (fast-forward). "
                    f"Сохраните свои правки или сделайте reset.\n{out}"
                )
        parts.append(f"Код обновлён с origin/{target}.")
    else:
        code, out = _run(["git", "pull", "--ff-only"], cwd=root)
        if code != 0:
            return f"git pull не удался.\n{out}"
        parts.append("Код обновлён (git pull).")

    code, log = _run(["git", "log", "-1", "--oneline"], cwd=root)
    if code == 0 and log:
        parts.append(f"Сейчас: {log}")

    if install_deps:
        req = root / "requirements.txt"
        if req.exists():
            code, out = _run(
                [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
                cwd=root,
            )
            if code != 0:
                parts.append("Зависимости: ошибка pip (можно проигнорировать, если уже стоят).")
                parts.append(out[-400:])
            else:
                parts.append("Зависимости проверены (pip).")

    parts.append("Перезапустите Jarvis, чтобы подхватить изменения.")
    return " ".join(parts)


def status_text() -> str:
    root = project_root()
    if getattr(sys, "frozen", False):
        return f"JARVIS.exe, сборка {BUILD}. Обновляется автоматически из GitHub Releases."
    if not is_git_checkout(root):
        return "Папка без git. Клонируйте репозиторий один раз, дальше — update.bat."
    branch = current_branch(root) or "?"
    code, log = _run(["git", "log", "-1", "--oneline"], cwd=root)
    tip = log if code == 0 else ""
    return f"Git: ветка {branch}. {tip}".strip()


# --- Version display ---------------------------------------------------------

_LAST_BUILD_KEY = "last_seen_build"


def version_label() -> str:
    """Short human label: «сборка 5» for the exe, «dev abc1234» for a source checkout."""
    if BUILD:
        return f"сборка {BUILD}"
    root = project_root()
    if is_git_checkout(root):
        code, sha = _run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
        if code == 0 and sha:
            return f"dev {sha}"
    return "dev"


def take_update_notice() -> str | None:
    """Message to show once after the exe was replaced by a newer build."""
    if not BUILD:
        return None
    from jarvis import memory

    previous = memory.get_settings().get(_LAST_BUILD_KEY)
    if previous == BUILD:
        return None
    memory.update_settings(**{_LAST_BUILD_KEY: BUILD})
    if isinstance(previous, int) and previous < BUILD:
        return f"JARVIS обновлён: сборка {previous} → {BUILD}."
    return None


# --- Background loop ---------------------------------------------------------


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
    cleanup_old_exes()
    if updates_disabled():
        return

    def _loop() -> None:
        stop = threading.Event()
        while True:
            check_and_update(on_status)
            stop.wait(CHECK_INTERVAL_SECONDS)

    threading.Thread(target=_loop, name="jarvis-updater", daemon=True).start()
