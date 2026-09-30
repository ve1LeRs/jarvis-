"""Text-to-speech via Edge TTS (online) with pyttsx3 fallback."""

from __future__ import annotations

import asyncio
import tempfile
import threading
from pathlib import Path

from jarvis import config

_speak_lock = threading.Lock()


def _play_mp3(path: Path) -> None:
    """Play an mp3 file cross-platform without blocking other threads wrongly."""
    import platform
    import subprocess
    import sys

    system = platform.system()
    try:
        if system == "Windows":
            # Prefer pygame if available; else PowerShell Media.SoundPlayer won't do mp3.
            try:
                import pygame

                pygame.mixer.init()
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(50)
                return
            except Exception:
                # ffplay / powershell fallback via start
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f'(New-Object Media.SoundPlayer "{path}").PlaySync()'
                        if path.suffix.lower() == ".wav"
                        else f"Add-Type -AssemblyName presentationCore; "
                        f"$p = New-Object System.Windows.Media.MediaPlayer; "
                        f'$p.Open([uri]"{path}"); $p.Play(); '
                        f"Start-Sleep -Milliseconds 500; "
                        f"while($p.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 50}}; "
                        f"Start-Sleep -Seconds $p.NaturalDuration.TimeSpan.TotalSeconds",
                    ],
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return
        if system == "Darwin":
            subprocess.run(["afplay", str(path)], check=False)
            return
        # Linux
        for player in ("ffplay", "mpg123", "mpv", "paplay"):
            from shutil import which

            if which(player):
                if player == "ffplay":
                    subprocess.run(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
                        check=False,
                    )
                else:
                    subprocess.run([player, str(path)], check=False)
                return
        # Last resort: playsound
        from playsound import playsound

        playsound(str(path))
    except Exception as exc:  # noqa: BLE001
        print(f"[TTS playback] {exc}", file=sys.stderr)


async def _edge_say(text: str) -> Path | None:
    try:
        import edge_tts

        communicate = edge_tts.Communicate(
            text,
            voice=config.TTS_VOICE,
            rate=config.TTS_RATE,
            volume=config.TTS_VOLUME,
        )
        tmp = Path(tempfile.gettempdir()) / "jarvis_speech.mp3"
        await communicate.save(str(tmp))
        return tmp
    except Exception as exc:  # noqa: BLE001
        print(f"[edge-tts] {exc}")
        return None


def _pyttsx3_say(text: str) -> None:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        # Prefer a Russian voice if installed.
        for voice in engine.getProperty("voices"):
            name = (voice.name or "").lower()
            lang = " ".join(getattr(voice, "languages", []) or []).lower()
            if "ru" in name or "russ" in name or "ru" in lang:
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:  # noqa: BLE001
        print(f"[pyttsx3] {exc}")
        print(f"JARVIS: {text}")


def speak(text: str, *, block: bool = True) -> None:
    """Speak text aloud. Falls back to console print if TTS fails."""
    text = (text or "").strip()
    if not text:
        return

    def _run() -> None:
        with _speak_lock:
            try:
                path = asyncio.run(_edge_say(text))
                if path and path.exists():
                    _play_mp3(path)
                    return
            except Exception as exc:  # noqa: BLE001
                print(f"[speak] {exc}")
            _pyttsx3_say(text)

    if block:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()
