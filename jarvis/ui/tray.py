"""System tray icon for background mode (Windows)."""

from __future__ import annotations

import threading
from typing import Callable

from jarvis import memory
from jarvis import updater


def run_tray(
    *,
    on_show: Callable[[], None] | None = None,
    on_quit: Callable[[], None] | None = None,
    on_mute_toggle: Callable[[], None] | None = None,
    status_provider: Callable[[], str] | None = None,
) -> None:
    """Block in tray until user quits. Falls back to no-op if pystray missing."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("pystray/Pillow не установлены — трей недоступен. Работаю в фоне без иконки.")
        if on_quit is None:
            threading.Event().wait()
        return

    version = updater.version_label()

    def _icon_image() -> "Image.Image":
        img = Image.new("RGB", (64, 64), color=(5, 11, 18))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, 56, 56), outline=(0, 229, 255), width=3)
        draw.ellipse((24, 24, 40, 40), fill=(0, 229, 255))
        return img

    def _notify(icon: "pystray.Icon", message: str) -> None:
        try:
            icon.notify(message, "J.A.R.V.I.S.")
        except Exception:  # noqa: BLE001
            print(message)

    def _quit(icon: "pystray.Icon", _item: object) -> None:
        icon.stop()
        if on_quit:
            on_quit()

    def _show(_icon: "pystray.Icon", _item: object) -> None:
        if on_show:
            on_show()

    def _mute(_icon: "pystray.Icon", _item: object) -> None:
        if on_mute_toggle:
            on_mute_toggle()
        else:
            memory.set_muted(not memory.is_muted())

    def _mute_label(_item: object) -> str:
        return "Включить голос" if memory.is_muted() else "Выключить голос"

    def _check_updates(icon: "pystray.Icon", _item: object) -> None:
        def _run() -> None:
            _notify(icon, "Проверяю обновления…")
            # Restarts the process itself when a newer build is found.
            _notify(icon, updater.update_from_git(install_deps=False))

        threading.Thread(target=_run, daemon=True).start()

    def _setup(icon: "pystray.Icon") -> None:
        icon.visible = True
        notice = updater.take_update_notice()
        if notice:
            _notify(icon, notice)

    menu = pystray.Menu(
        pystray.MenuItem(f"J.A.R.V.I.S. — {version}", lambda: None, enabled=False),
        pystray.MenuItem("Показать окно", _show) if on_show else pystray.Menu.SEPARATOR,
        pystray.MenuItem(_mute_label, _mute),
        pystray.MenuItem("Проверить обновления", _check_updates),
        pystray.MenuItem("Выход", _quit),
    )
    icon = pystray.Icon("jarvis", _icon_image(), f"J.A.R.V.I.S. ({version})", menu)
    icon.run(setup=_setup)
