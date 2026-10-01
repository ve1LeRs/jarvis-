# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — build on Windows: pyinstaller jarvis.spec"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    "jarvis",
    "jarvis.__main__",
    "jarvis.config",
    "jarvis.commands",
    "jarvis.listen",
    "jarvis.speak",
    "jarvis.autostart",
    "jarvis.actions",
    "jarvis.actions.system",
    "jarvis.ui",
    "jarvis.ui.hud",
    "jarvis.ui.tray",
    "speech_recognition",
    "edge_tts",
    "pyttsx3",
    "pygame",
    "pystray",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "comtypes",
    "winsound",
]

for pkg in ("speech_recognition", "edge_tts", "pystray", "pyttsx3", "pygame"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

try:
    hiddenimports += collect_submodules("pyttsx3")
except Exception:
    pass

a = Analysis(
    ["JARVIS.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
