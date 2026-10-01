"""Global push-to-talk hotkey (Windows; no-op elsewhere)."""

from __future__ import annotations

import os
import platform
import threading
from typing import Callable

SYSTEM = platform.system()

# Default: Ctrl+Alt+J
DEFAULT_VK = int(os.getenv("JARVIS_PTT_VK", "0x4A"), 0)  # J
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4A21


class PushToTalk:
    """Register a system hotkey and invoke callback when pressed."""

    def __init__(
        self,
        on_press: Callable[[], None],
        *,
        vk: int = DEFAULT_VK,
        modifiers: int = MOD_CONTROL | MOD_ALT,
    ) -> None:
        self.on_press = on_press
        self.vk = vk
        self.modifiers = modifiers
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.error: str | None = None

    def start(self) -> bool:
        if SYSTEM != "Windows":
            self.error = "Push-to-talk доступен только на Windows."
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)
        return self.error is None

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            self._ready.set()
            return

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        if not user32.RegisterHotKey(None, HOTKEY_ID, self.modifiers, self.vk):
            self.error = "Не удалось зарегистрировать горячую клавишу (занята?)."
            self._ready.set()
            return
        self._ready.set()

        msg = wintypes.MSG()
        while not self._stop.is_set():
            # Peek so we can exit cleanly
            has = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
            if has and msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                try:
                    self.on_press()
                except Exception:
                    pass
            else:
                self._stop.wait(0.05)
        user32.UnregisterHotKey(None, HOTKEY_ID)


def describe_default() -> str:
    return "Push-to-talk: Ctrl+Alt+J (без слова «Джарвис»). Задайте JARVIS_PTT_VK для другой клавиши."
