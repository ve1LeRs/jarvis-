"""Cinematic HUD for J.A.R.V.I.S."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from jarvis import config
from jarvis import memory
from jarvis import updater


class JarvisHUD:
    def __init__(self) -> None:
        version = updater.version_label()
        self.root = tk.Tk()
        self.root.title(f"{config.WINDOW_TITLE} — {version}")
        self.root.configure(bg=config.BG)
        self.root.geometry("760x480")
        self.root.minsize(600, 400)

        title_font = tkfont.Font(family="Segoe UI", size=28, weight="bold")
        mono = tkfont.Font(family="Consolas", size=12)
        status_font = tkfont.Font(family="Segoe UI", size=14)
        small = tkfont.Font(family="Segoe UI", size=11)

        header = tk.Frame(self.root, bg=config.BG)
        header.pack(fill="x", padx=24, pady=(24, 8))

        top_row = tk.Frame(header, bg=config.BG)
        top_row.pack(fill="x")

        self.title_label = tk.Label(
            top_row,
            text="J.A.R.V.I.S.",
            fg=config.ACCENT,
            bg=config.BG,
            font=title_font,
        )
        self.title_label.pack(side="left", anchor="w")

        self.mode_badge = tk.Label(
            top_row,
            text="ONLINE",
            fg=config.BG,
            bg=config.ACCENT,
            font=small,
            padx=8,
            pady=2,
        )
        self.mode_badge.pack(side="right", anchor="e", pady=8)

        self.subtitle = tk.Label(
            header,
            text=f"Just A Rather Very Intelligent System · {version}",
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
            wraplength=700,
            justify="left",
        )
        self.status.pack(fill="x", padx=24, pady=(16, 8))

        controls = tk.Frame(self.root, bg=config.BG)
        controls.pack(fill="x", padx=24, pady=(0, 8))

        self.mute_btn = tk.Button(
            controls,
            text="Голос: вкл",
            command=self._toggle_mute,
            bg="#0A1620",
            fg=config.ACCENT,
            activebackground="#122433",
            activeforeground=config.FG,
            relief="flat",
            padx=12,
            pady=4,
            font=small,
        )
        self.mute_btn.pack(side="left")

        hint = tk.Label(
            controls,
            text="Скажите «Джарвис» · Esc — свернуть",
            fg="#6FA8B8",
            bg=config.BG,
            font=small,
        )
        hint.pack(side="right")

        log_frame = tk.Frame(
            self.root,
            bg="#0A1620",
            highlightbackground=config.ACCENT,
            highlightthickness=1,
        )
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

        self.root.bind("<Escape>", lambda _e: self.root.iconify())
        self._pulse_on = False
        self._refresh_mute_label()
        self._pulse()

    def _refresh_mute_label(self) -> None:
        muted = memory.is_muted()
        self.mute_btn.configure(text="Голос: выкл" if muted else "Голос: вкл")
        self.mode_badge.configure(
            text="MUTED" if muted else "ONLINE",
            bg="#FF6B6B" if muted else config.ACCENT,
        )

    def _toggle_mute(self) -> None:
        memory.set_muted(not memory.is_muted())
        self._refresh_mute_label()
        state = "выключен" if memory.is_muted() else "включён"
        self.set_status(f"Голос {state}.")

    def set_status(self, text: str) -> None:
        def _apply() -> None:
            self.status.configure(text=text)
            self._append_log(text)
            lowered = text.lower()
            if "слушаю" in lowered or "жду команду" in lowered:
                self.mode_badge.configure(text="LISTENING", bg="#7CFFB2", fg=config.BG)
            elif "распознаю" in lowered:
                self.mode_badge.configure(text="THINKING", bg="#FFD166", fg=config.BG)
            else:
                self._refresh_mute_label()

        self.root.after(0, _apply)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"> {text}\n")
        # Keep log reasonably short
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 200:
            self.log.delete("1.0", "50.0")
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
