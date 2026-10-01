"""Text-to-speech via Edge TTS (online) with pyttsx3 fallback."""

from __future__ import annotations

import asyncio
import os
import queue
import re
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
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
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


async def _edge_say(text: str, index: int = 0, *, attempts: int = 2) -> Path | None:
    try:
        import edge_tts
    except ImportError as exc:
        print(f"[edge-tts] {exc}")
        return None

    # Distinct file per chunk: the next one is written while the previous plays.
    tmp = Path(tempfile.gettempdir()) / f"jarvis_speech_{os.getpid()}_{index}.mp3"
    for attempt in range(attempts):
        try:
            communicate = edge_tts.Communicate(
                text,
                voice=config.TTS_VOICE,
                rate=config.TTS_RATE,
                volume=config.TTS_VOLUME,
            )
            await communicate.save(str(tmp))
            return tmp
        except Exception as exc:  # noqa: BLE001
            # The Edge service intermittently answers "No audio was received".
            print(f"[edge-tts] попытка {attempt + 1}: {exc}")
    return None


_SENTENCE_END = re.compile(r"(?<=[.!?…;])\s+")


def split_for_speech(
    text: str,
    *,
    first_min: int = 40,
    first_max: int = 140,
    max_len: int = 260,
) -> list[str]:
    """Split into speakable chunks: a short first one for fast start, larger ones after."""
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    pieces: list[str] = []
    for sentence in sentences:
        while len(sentence) > max_len:
            cut = sentence.rfind(",", 0, max_len)
            cut = cut if cut > max_len // 3 else sentence.rfind(" ", 0, max_len)
            if cut <= 0:
                cut = max_len
            pieces.append(sentence[: cut + 1].strip())
            sentence = sentence[cut + 1 :].strip()
        if sentence:
            pieces.append(sentence)

    chunks: list[str] = []
    for piece in pieces:
        if not chunks:
            chunks.append(piece)
            continue
        last = chunks[-1]
        fits = len(last) + 1 + len(piece)
        if len(chunks) == 1:
            merge = len(last) < first_min and fits <= first_max
        else:
            merge = fits <= max_len
        if merge:
            chunks[-1] = f"{last} {piece}"
        else:
            chunks.append(piece)
    return chunks


def _speak_streaming(text: str) -> None:
    """Synthesize chunk N+1 while chunk N is playing."""
    chunks = split_for_speech(text)
    ready: queue.Queue[tuple[str, Path | None] | None] = queue.Queue(maxsize=2)

    def _produce() -> None:
        for i, chunk in enumerate(chunks):
            try:
                path = asyncio.run(_edge_say(chunk, i))
            except Exception as exc:  # noqa: BLE001
                print(f"[speak] {exc}")
                path = None
            ready.put((chunk, path))
        ready.put(None)

    threading.Thread(target=_produce, daemon=True).start()
    while (item := ready.get()) is not None:
        chunk, path = item
        if path and path.exists():
            _play_mp3(path)
            try:
                path.unlink()
            except OSError:
                pass
        else:
            _pyttsx3_say(chunk)


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

    try:
        from jarvis import memory

        if memory.is_muted():
            print(f"JARVIS: {text}")
            return
    except Exception:
        pass

    def _run() -> None:
        with _speak_lock:
            _speak_streaming(text)

    if block:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()
