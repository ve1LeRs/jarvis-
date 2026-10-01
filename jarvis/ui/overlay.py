"""Compact always-on-top overlay HUD."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from jarvis import config
from jarvis import context
from jarvis import memory


class JarvisOverlay:
    """Small status strip instead of the full window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.configure(bg=config.BG)
        self.root.geometry("420x96+40+40")
        self.root.resizable(False, False)
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.root.attributes("-alpha", 0.94)
        except tk.TclError:
            pass

        title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        small = tkfont.Font(family="Segoe UI", size=10)

        wrap = tk.Frame(self.root, bg=config.BG, padx=12, pady=10)
        wrap.pack(fill="both", expand=True)

        top = tk.Frame(wrap, bg=config.BG)
        top.pack(fill="x")

        self.title = tk.Label(top, text="J.A.R.V.I.S.", fg=config.ACCENT, bg=config.BG, font=title_font)
        self.title.pack(side="left")

        self.badge = tk.Label(
            top,
            text="ONLINE",
            fg=config.BG,
            bg=config.ACCENT,
            font=small,
            padx=6,
            pady=1,
        )
        self.badge.pack(side="right")

        self.status = tk.Label(
            wrap,
            text="Готов",
            fg=config.FG,
            bg=config.BG,
            font=small,
            wraplength=390,
            justify="left",
            anchor="w",
        )
        self.status.pack(fill="x", pady=(8, 0))

        self.root.bind("<Escape>", lambda _e: self.root.withdraw())
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self._pulse_on = False
        self._pulse()

    def set_status(self, text: str) -> None:
        def _apply() -> None:
            self.status.configure(text=text)
            lowered = text.lower()
            ctx = context.get()
            if memory.is_muted():
                self.badge.configure(text="MUTED", bg="#FF6B6B")
            elif "слушаю" in lowered or "жду команду" in lowered:
                self.badge.configure(text="LISTENING", bg="#7CFFB2")
            elif ctx.mode == "game":
                self.badge.configure(text="GAME", bg="#FF9F1C")
            elif ctx.mode in {"work", "code"}:
                self.badge.configure(text=ctx.mode.upper(), bg="#4CC9F0")
            else:
                self.badge.configure(text="ONLINE", bg=config.ACCENT)

        self.root.after(0, _apply)

    def _pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self.title.configure(fg=config.ACCENT if self._pulse_on else "#007A88")
        self.root.after(900, self._pulse)

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.root.after(0, self.root.destroy)
