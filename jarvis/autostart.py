"""Windows autostart and desktop shortcut helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "J.A.R.V.I.S."
SHORTCUT_NAME = "JARVIS.lnk"
STARTUP_VBS_NAME = "JARVIS_autostart.vbs"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def python_exe() -> Path:
    """Prefer venv python if present."""
    root = project_root()
    venv_py = root / ".venv" / "Scripts" / "pythonw.exe"
    if venv_py.exists():
        return venv_py
    venv_py = root / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return venv_py
    # pythonw hides console — better for background
    candidate = Path(sys.executable)
    pythonw = candidate.with_name("pythonw.exe")
    if pythonw.exists():
        return pythonw
    return candidate


def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA не найден — автозапуск только для Windows.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def desktop_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(userprofile) / "Desktop"


def _write_vbs_launcher(path: Path) -> None:
    """VBScript starts JARVIS without a black console window."""
    root = project_root()
    py = python_exe()
    # --background: voice + tray/HUD minimized, no console banner needed
    script = f'''Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "{root}"
sh.Run """{py}"" -m jarvis --background", 0, False
'''
    path.write_text(script, encoding="utf-8")


def _create_shortcut(lnk_path: Path, target: Path, arguments: str, workdir: Path, description: str) -> None:
    """Create .lnk via PowerShell (no extra Python deps)."""
    import subprocess

    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{lnk_path}')
$s.TargetPath = '{target}'
$s.Arguments = '{arguments}'
$s.WorkingDirectory = '{workdir}'
$s.Description = '{description}'
$s.WindowStyle = 7
$s.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        creationflags=getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0),
    )


def enable_autostart() -> str:
    """Put a silent launcher into the Windows Startup folder."""
    if os.name != "nt":
        return "Автозапуск поддерживается только на Windows."

    folder = startup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    vbs = folder / STARTUP_VBS_NAME
    _write_vbs_launcher(vbs)
    return f"Автозапуск включён.\nПри входе в Windows будет запускаться:\n{vbs}"


def disable_autostart() -> str:
    if os.name != "nt":
        return "Автозапуск поддерживается только на Windows."

    vbs = startup_dir() / STARTUP_VBS_NAME
    lnk = startup_dir() / SHORTCUT_NAME
    removed = []
    for path in (vbs, lnk):
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
    py = python_exe()
    # Prefer .bat for double-click (shows window); desktop can also use pythonw+background
    bat = root / "start_jarvis.bat"
    lnk = desktop_dir() / SHORTCUT_NAME
    if bat.exists():
        _create_shortcut(lnk, bat, "", root, APP_NAME)
    else:
        _create_shortcut(lnk, py, "-m jarvis", root, APP_NAME)
    return f"Ярлык создан: {lnk}"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="JARVIS autostart manager")
    parser.add_argument("action", choices=["enable", "disable", "status", "desktop"])
    args = parser.parse_args(argv)

    if args.action == "enable":
        print(enable_autostart())
    elif args.action == "disable":
        print(disable_autostart())
    elif args.action == "desktop":
        print(create_desktop_shortcut())
    else:
        print("Автозапуск: ВКЛ" if is_autostart_enabled() else "Автозапуск: ВЫКЛ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
