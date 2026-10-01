"""Text-to-speech: Edge TTS (male Russian) with a careful offline fallback.

Always finishes one utterance with a single engine — never mixes Edge + SAPI
in the middle of a phrase (that sounds like male → female robot).
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from jarvis import config

_speak_lock = threading.Lock()
_pygame_ready = False
_EDGE_RETRIES = 3


def _ensure_pygame() -> bool:
    global _pygame_ready
    if _pygame_ready:
        return True
    try:
        import pygame

        # Explicit audio init — more reliable than mixer.init() defaults on Windows.
        pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=1024)
        _pygame_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[TTS] pygame unavailable: {exc}", file=sys.stderr)
        return False


def _play_mp3(path: Path) -> bool:
    """Play mp3 and wait until finished. Returns True on success."""
    import platform
    import subprocess

    system = platform.system()

    # 1) pygame — preferred (bundled in requirements / exe)
    if _ensure_pygame():
        try:
            import pygame

            # Unload previous music so Windows releases the file handle.
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(40)
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[TTS pygame] {exc}", file=sys.stderr)

    try:
        if system == "Windows":
            # MediaPlayer can play mp3; SoundPlayer cannot.
            # Unique variable scope per call; wait on Position vs duration.
            ps = f"""
            Add-Type -AssemblyName presentationCore
            $p = New-Object System.Windows.Media.MediaPlayer
            $p.Open([Uri]::new('{path.as_posix()}'))
            $sw = [Diagnostics.Stopwatch]::StartNew()
            while (-not $p.NaturalDuration.HasTimeSpan) {{
                if ($sw.Elapsed.TotalSeconds -gt 8) {{ break }}
                Start-Sleep -Milliseconds 40
            }}
            if (-not $p.NaturalDuration.HasTimeSpan) {{ exit 1 }}
            $p.Play()
            $total = $p.NaturalDuration.TimeSpan.TotalMilliseconds
            while ($p.Position.TotalMilliseconds + 40 -lt $total) {{
                Start-Sleep -Milliseconds 40
            }}
            Start-Sleep -Milliseconds 120
            $p.Close()
            """
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return completed.returncode == 0

        if system == "Darwin":
            return subprocess.run(["afplay", str(path)], check=False).returncode == 0

        from shutil import which

        for player in ("ffplay", "mpg123", "mpv"):
            if which(player):
                if player == "ffplay":
                    rc = subprocess.run(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
                        check=False,
                    ).returncode
                elif player == "mpv":
                    rc = subprocess.run(
                        ["mpv", "--no-video", "--really-quiet", str(path)],
                        check=False,
                    ).returncode
                else:
                    rc = subprocess.run([player, str(path)], check=False).returncode
                return rc == 0

        from playsound import playsound

        playsound(str(path))
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[TTS playback] {exc}", file=sys.stderr)
        return False


async def _edge_synthesize(text: str, out: Path) -> bool:
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice=config.TTS_VOICE,
        rate=config.TTS_RATE,
        volume=config.TTS_VOLUME,
        pitch=config.TTS_PITCH,
    )
    await communicate.save(str(out))
    return out.exists() and out.stat().st_size > 0


def _edge_say(text: str) -> Path | None:
    """Synthesize with Edge TTS; retry on transient network / file errors."""
    tmp_dir = Path(tempfile.gettempdir())
    for attempt in range(1, _EDGE_RETRIES + 1):
        out = tmp_dir / f"jarvis_speech_{uuid.uuid4().hex}.mp3"
        try:
            ok = asyncio.run(_edge_synthesize(text, out))
            if ok:
                return out
        except Exception as exc:  # noqa: BLE001
            print(f"[edge-tts] attempt {attempt}/{_EDGE_RETRIES}: {exc}", file=sys.stderr)
        try:
            if out.exists():
                out.unlink(missing_ok=True)  # type: ignore[call-arg]
        except Exception:
            pass
        time.sleep(0.35 * attempt)
    return None


def _pick_male_russian_voice(engine) -> str | None:
    """Prefer a male RU voice for SAPI fallback; never pick Zira/Irina if avoidable."""
    voices = list(engine.getProperty("voices") or [])
    scored: list[tuple[int, str]] = []
    for voice in voices:
        name = (voice.name or "").lower()
        vid = (voice.id or "").lower()
        langs = " ".join(
            (x.decode() if isinstance(x, bytes) else str(x)).lower()
            for x in (getattr(voice, "languages", None) or [])
        )
        blob = f"{name} {vid} {langs}"
        score = 0
        if any(k in blob for k in ("ru", "russ", "416", "ru-ru")):
            score += 10
        # Known male / JARVIS-like
        if any(k in blob for k in ("pavel", "dmitry", "dmitri", "male", "мужск", "david", "mark")):
            score += 20
        # Push female / robotic defaults down hard
        if any(k in blob for k in ("irina", "zira", "helena", "female", "женск", "hazel")):
            score -= 30
        if score:
            scored.append((score, voice.id))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _pyttsx3_say(text: str) -> None:
    """Offline fallback — still try to stay male Russian, one engine only."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
        chosen = _pick_male_russian_voice(engine)
        if chosen:
            engine.setProperty("voice", chosen)
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 1.0)
        engine.say(text)
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        print(f"[pyttsx3] {exc}", file=sys.stderr)
        print(f"JARVIS: {text}")


def speak(text: str, *, block: bool = True) -> None:
    """Speak text aloud with one consistent voice per utterance."""
    text = (text or "").strip()
    if not text:
        return

    def _run() -> None:
        with _speak_lock:
            temp_paths: list[Path] = []
            try:
                path = _edge_say(text)
                if path is not None:
                    temp_paths.append(path)
                    if _play_mp3(path):
                        return
                    print("[TTS] playback failed, retrying Edge once…", file=sys.stderr)
                    path2 = _edge_say(text)
                    if path2 is not None:
                        temp_paths.append(path2)
                        if _play_mp3(path2):
                            return
            except Exception as exc:  # noqa: BLE001
                print(f"[speak] {exc}", file=sys.stderr)
            finally:
                for p in temp_paths:
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass
            # Last resort only — whole phrase, never mixed with Edge mid-sentence.
            _pyttsx3_say(text)

    if block:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()
