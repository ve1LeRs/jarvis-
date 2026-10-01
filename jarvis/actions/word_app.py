"""Microsoft Word helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path

from jarvis.actions import launch


def _find_word() -> str | None:
    return launch.which_or_path(
        "WINWORD",
        [
            r"%ProgramFiles%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%ProgramFiles(x86)%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%ProgramFiles%\Microsoft Office\Office16\WINWORD.EXE",
            r"%ProgramFiles%\Microsoft Office\root\Office15\WINWORD.EXE",
        ],
    )


def open_word(path: str | None = None) -> str:
    exe = _find_word()
    target = (path or "").strip()
    if target:
        expanded = os.path.expandvars(os.path.expanduser(target))
        if not Path(expanded).exists():
            # Search Documents for a matching name
            found = _find_document(target)
            if found:
                expanded = found
        if exe and Path(expanded).exists():
            launch.run([exe, expanded])
            launch.focus_window(["word", "microsoft word"])
            return f"Открываю в Word: {Path(expanded).name}."
        if Path(expanded).exists() and launch.open_uri(expanded):
            return f"Открываю документ: {Path(expanded).name}."
        return f"Документ «{target}» не найден."

    if exe:
        launch.run([exe])
        launch.focus_window(["word", "microsoft word"])
        return "Открываю Word."
    # Protocol / start menu fallback
    launch.run("winword", shell=True)
    return "Пытаюсь открыть Word."


def new_document() -> str:
    exe = _find_word()
    if exe:
        launch.run([exe])
        time.sleep(0.8)
        launch.focus_window(["word", "microsoft word"])
        if launch.send_hotkey("ctrl", "n"):
            return "Создаю новый документ Word."
        return "Открыл Word — нажмите Ctrl+N, если документ не создался."
    launch.run("winword", shell=True)
    return "Открываю Word для нового документа."


def _find_document(name: str) -> str | None:
    needle = name.lower().replace(".docx", "").replace(".doc", "").strip()
    roots = [
        Path.home() / "Documents",
        Path.home() / "Документы",
        Path.home() / "Desktop",
        Path.home() / "Рабочий стол",
        Path.home() / "Downloads",
    ]
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".doc", ".docx", ".rtf", ".odt"}:
                    continue
                if needle in path.stem.lower():
                    return str(path)
        except OSError:
            continue
    return None


def focus_word() -> str:
    if launch.focus_window(["word", "microsoft word"]):
        return "Переключаюсь на Word."
    return open_word()


def save_document() -> str:
    launch.focus_window(["word", "microsoft word"])
    if launch.send_hotkey("ctrl", "s"):
        return "Сохраняю документ Word."
    return "Не удалось сохранить — сфокусируйте Word."
