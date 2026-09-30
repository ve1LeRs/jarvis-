"""System tray icon for background mode (Windows)."""

from __future__ import annotations

import threading
from typing import Callable


def run_tray(
    *,
    on_show: Callable[[], None] | None = None,
    on_quit: Callable[[], None] | None = None,
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

    def _icon_image() -> "Image.Image":
        img = Image.new("RGB", (64, 64), color=(5, 11, 18))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, 56, 56), outline=(0, 229, 255), width=3)
        draw.ellipse((24, 24, 40, 40), fill=(0, 229, 255))
        return img

    def _quit(icon: "pystray.Icon", _item: object) -> None:
        icon.stop()
        if on_quit:
            on_quit()

    def _show(icon: "pystray.Icon", _item: object) -> None:
        if on_show:
            on_show()

    menu = pystray.Menu(
        pystray.MenuItem("J.A.R.V.I.S. активен", lambda: None, enabled=False),
        pystray.MenuItem("Показать окно", _show) if on_show else pystray.Menu.SEPARATOR,
        pystray.MenuItem("Выход", _quit),
    )
    icon = pystray.Icon("jarvis", _icon_image(), "J.A.R.V.I.S.", menu)
    icon.run()
