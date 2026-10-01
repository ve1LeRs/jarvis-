"""Update Jarvis from git without re-downloading the whole project."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


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


def update_from_git(
    *,
    branch: str | None = None,
    install_deps: bool = True,
) -> str:
    """git fetch + pull (ff-only) and optionally refresh pip requirements."""
    root = project_root()
    if getattr(sys, "frozen", False):
        return (
            "Собранный JARVIS.exe обновляется пересборкой из папки с исходниками. "
            "Клонируйте репозиторий один раз и запускайте update.bat / «обнови джарвис»."
        )
    if not is_git_checkout(root):
        return (
            "Это не git-клон. Один раз сделайте:\n"
            "  git clone https://github.com/ve1LeRs/jarvis-.git\n"
            "дальше обновляйтесь через update.bat — скачивать архив заново не нужно."
        )

    code, which = _run(["git", "--version"], cwd=root)
    if code != 0:
        return "Git не найден. Установите Git for Windows: https://git-scm.com/download/win"

    parts: list[str] = []
    target = (branch or os.getenv("JARVIS_UPDATE_BRANCH") or "").strip()
    if not target:
        target = current_branch(root) or "main"

    code, out = _run(["git", "fetch", "--prune", "origin"], cwd=root)
    if code != 0:
        return f"Не удалось связаться с origin.\n{out}"

    # Prefer remote branch if it exists
    code, _ = _run(["git", "rev-parse", "--verify", f"origin/{target}"], cwd=root)
    if code == 0:
        code, out = _run(
            ["git", "pull", "--ff-only", "origin", target],
            cwd=root,
        )
        if code != 0:
            # try checkout tracking then pull
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
            py = sys.executable
            code, out = _run(
                [py, "-m", "pip", "install", "-r", str(req), "-q"],
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
        return "Запущен из exe — для обновлений используйте папку с git-клоном."
    if not is_git_checkout(root):
        return "Папка без git. Клонируйте репозиторий один раз, дальше — update.bat."
    branch = current_branch(root) or "?"
    code, log = _run(["git", "log", "-1", "--oneline"], cwd=root)
    tip = log if code == 0 else ""
    return f"Git: ветка {branch}. {tip}".strip()
