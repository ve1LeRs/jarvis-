"""Windows app registration: shortcuts, Start Menu, autostart."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


APP_NAME = "J.A.R.V.I.S."
SHORTCUT_NAME = "JARVIS.lnk"
STARTUP_VBS_NAME = "JARVIS_autostart.vbs"
START_MENU_FOLDER = "J.A.R.V.I.S"


def project_root() -> Path:
    # When frozen by PyInstaller, use the folder with the .exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def python_exe() -> Path:
    """Prefer venv pythonw; when frozen, the .exe itself."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    root = project_root()
    for name in ("pythonw.exe", "python.exe"):
        venv_py = root / ".venv" / "Scripts" / name
        if venv_py.exists():
            return venv_py
    candidate = Path(sys.executable)
    pythonw = candidate.with_name("pythonw.exe")
    if pythonw.exists():
        return pythonw
    return candidate


def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA не найден — только Windows.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def desktop_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE") or str(Path.home())
    # Prefer Russian/localized Desktop via shell folder when possible
    return Path(userprofile) / "Desktop"


def start_menu_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA не найден — только Windows.")
    path = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_shortcut(
    lnk_path: Path,
    target: Path,
    arguments: str,
    workdir: Path,
    description: str,
    *,
    window_style: int = 7,
) -> None:
    # Escape single quotes for PowerShell single-quoted strings
    def q(value: object) -> str:
        return str(value).replace("'", "''")

    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{q(lnk_path)}')
$s.TargetPath = '{q(target)}'
$s.Arguments = '{q(arguments)}'
$s.WorkingDirectory = '{q(workdir)}'
$s.Description = '{q(description)}'
$s.WindowStyle = {window_style}
$s.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _launch_target_and_args(*, background: bool) -> tuple[Path, str]:
    """Return (executable, arguments) for starting JARVIS."""
    root = project_root()
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return exe, "--background" if background else ""

    py = python_exe()
    args = "-m jarvis --background" if background else "-m jarvis"
    return py, args


def _write_vbs_launcher(path: Path) -> None:
    root = project_root()
    target, args = _launch_target_and_args(background=True)
    script = f'''Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "{root}"
sh.Run """{target}"" {args}", 0, False
'''
    path.write_text(script, encoding="utf-8")


def enable_autostart() -> str:
    if os.name != "nt":
        return "Автозапуск поддерживается только на Windows."

    folder = startup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    vbs = folder / STARTUP_VBS_NAME
    _write_vbs_launcher(vbs)
    return f"Автозапуск включён.\n{vbs}"


def disable_autostart() -> str:
    if os.name != "nt":
        return "Автозапуск поддерживается только на Windows."

    removed = []
    for path in (startup_dir() / STARTUP_VBS_NAME, startup_dir() / SHORTCUT_NAME):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if not removed:
        return "Автозапуск уже выключен."
    return "Автозапуск отключён:\n" + "\n".join(removed)


def is_autostart_enabled() -> bool:
    try:
        folder = startup_dir()
    except RuntimeError:
        return False
    return (folder / STARTUP_VBS_NAME).exists() or (folder / SHORTCUT_NAME).exists()


def create_desktop_shortcut() -> str:
    if os.name != "nt":
        return "Ярлык на рабочий стол — только Windows."

    root = project_root()
    target, args = _launch_target_and_args(background=True)
    lnk = desktop_dir() / SHORTCUT_NAME
    _create_shortcut(lnk, target, args, root, APP_NAME, window_style=7)
    return f"Ярлык на рабочем столе: {lnk}"


def create_start_menu_shortcuts() -> str:
    if os.name != "nt":
        return "Меню Пуск — только Windows."

    root = project_root()
    menu = start_menu_dir()
    target_bg, args_bg = _launch_target_and_args(background=True)
    target_ui, args_ui = _launch_target_and_args(background=False)

    _create_shortcut(menu / "JARVIS.lnk", target_bg, args_bg, root, f"{APP_NAME} (фон)")
    _create_shortcut(menu / "JARVIS — окно.lnk", target_ui, args_ui, root, f"{APP_NAME} с окном")

    uninstall = root / "uninstall.bat"
    if uninstall.exists():
        _create_shortcut(menu / "Удалить JARVIS.lnk", uninstall, "", root, "Удалить JARVIS")

    update = root / "update.bat"
    if update.exists():
        _create_shortcut(menu / "Обновить JARVIS.lnk", update, "", root, "Обновить JARVIS (git pull)")

    dev = root / "dev.bat"
    if dev.exists():
        _create_shortcut(menu / "JARVIS — тест (dev).lnk", dev, "", root, "Быстрый текстовый тест")

    return f"Ярлыки в меню Пуск: {menu}"


def install_as_app(*, with_autostart: bool = True) -> str:
    """One-shot: desktop + Start Menu + optional autostart — like a normal program."""
    if os.name != "nt":
        return "Установка как приложения — только Windows."

    lines = [
        create_desktop_shortcut(),
        create_start_menu_shortcuts(),
    ]
    if with_autostart:
        lines.append(enable_autostart())
    try:
        from jarvis import paths as paths_mod
        from jarvis import plugins

        found = paths_mod.detect_all()
        lines.append(f"Автопоиск программ: найдено {len(found)}.")
        plugins.ensure_dir()
        lines.append(f"Папка плагинов: {plugins.PLUGINS_DIR}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"Профиль ПК: пропуск ({exc}).")
    lines.append(
        "Готово: JARVIS установлен как программа — ярлык на рабочем столе, "
        "пункт в меню Пуск"
        + (", автозапуск при включении ПК." if with_autostart else ".")
    )
    return "\n".join(lines)


def uninstall_app() -> str:
    if os.name != "nt":
        return "Удаление — только Windows."

    removed: list[str] = []
    for path in (
        desktop_dir() / SHORTCUT_NAME,
        startup_dir() / STARTUP_VBS_NAME,
        startup_dir() / SHORTCUT_NAME,
    ):
        if path.exists():
            path.unlink()
            removed.append(str(path))

    menu = None
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            menu = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER
            if menu.exists():
                for child in menu.iterdir():
                    child.unlink(missing_ok=True)
                    removed.append(str(child))
                menu.rmdir()
                removed.append(str(menu))
    except OSError:
        pass

    if not removed:
        return "Ярлыки уже удалены. Папку с программой можно удалить вручную."
    return "Удалены ярлыки и автозапуск:\n" + "\n".join(removed)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="JARVIS Windows app installer")
    parser.add_argument(
        "action",
        choices=["enable", "disable", "status", "desktop", "install", "uninstall", "startmenu"],
    )
    args = parser.parse_args(argv)

    actions = {
        "enable": enable_autostart,
        "disable": disable_autostart,
        "desktop": create_desktop_shortcut,
        "startmenu": create_start_menu_shortcuts,
        "install": install_as_app,
        "uninstall": uninstall_app,
        "status": lambda: ("Автозапуск: ВКЛ" if is_autostart_enabled() else "Автозапуск: ВЫКЛ"),
    }
    print(actions[args.action]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
