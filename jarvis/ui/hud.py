"""Minimal cinematic HUD for J.A.R.V.I.S."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from jarvis import config


class JarvisHUD:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.configure(bg=config.BG)
        self.root.geometry("720x420")
        self.root.minsize(560, 360)

        title_font = tkfont.Font(family="Segoe UI", size=28, weight="bold")
        mono = tkfont.Font(family="Consolas", size=12)
        status_font = tkfont.Font(family="Segoe UI", size=14)

        header = tk.Frame(self.root, bg=config.BG)
        header.pack(fill="x", padx=24, pady=(24, 8))

        self.title_label = tk.Label(
            header,
            text="J.A.R.V.I.S.",
            fg=config.ACCENT,
            bg=config.BG,
            font=title_font,
        )
        self.title_label.pack(anchor="w")

        self.subtitle = tk.Label(
            header,
            text="Just A Rather Very Intelligent System",
            fg="#6FA8B8",
            bg=config.BG,
            font=status_font,
        )
        self.subtitle.pack(anchor="w")

        self.status = tk.Label(
            self.root,
            text="Инициализация…",
            fg=config.FG,
            bg=config.BG,
            font=status_font,
            wraplength=660,
            justify="left",
        )
        self.status.pack(fill="x", padx=24, pady=(16, 8))

        log_frame = tk.Frame(self.root, bg="#0A1620", highlightbackground=config.ACCENT, highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=24, pady=(8, 24))

        self.log = tk.Text(
            log_frame,
            bg="#0A1620",
            fg=config.FG,
            insertbackground=config.ACCENT,
            font=mono,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=12,
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self._pulse_on = False
        self._pulse()

    def set_status(self, text: str) -> None:
        def _apply() -> None:
            self.status.configure(text=text)
            self._append_log(text)

        self.root.after(0, _apply)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"> {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        color = config.ACCENT if self._pulse_on else "#007A88"
        self.title_label.configure(fg=color)
        self.root.after(700, self._pulse)

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.root.after(0, self.root.destroy)
