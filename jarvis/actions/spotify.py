"""Spotify control: open app, search/play tracks, liked songs.

Works out of the box via Spotify desktop URIs on Windows.
Optional Web API (search + exact play) if credentials are set:

  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  SPOTIFY_REFRESH_TOKEN   # for real playback control / library
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SYSTEM = platform.system()

_TOKEN_CACHE: dict[str, object] = {"access": None, "expires": 0.0}


def _run(command: list[str] | str, *, shell: bool = False) -> None:
    kwargs: dict = {"shell": shell}
    if SYSTEM == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(command, **kwargs)


def _open_uri(uri: str) -> bool:
    """Open a spotify: or https:// URI with the OS handler."""
    try:
        if SYSTEM == "Windows":
            os.startfile(uri)  # type: ignore[attr-defined]
            return True
        if SYSTEM == "Darwin":
            _run(["open", uri])
            return True
        if shutil.which("xdg-open"):
            _run(["xdg-open", uri])
            return True
    except OSError:
        return False
    return False


def _find_spotify_exe() -> str | None:
    if SYSTEM != "Windows":
        return shutil.which("spotify")
    candidates = [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
        r"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic_*",
    ]
    for path in candidates:
        if "*" in path:
            continue
        if Path(path).exists():
            return path
    return shutil.which("spotify")


def open_spotify() -> str:
    exe = _find_spotify_exe()
    if exe:
        _run([exe])
        return "Открываю Spotify."
    if _open_uri("spotify:"):
        return "Открываю Spotify."
    if _open_uri("https://open.spotify.com"):
        return "Приложение не найдено — открываю Spotify в браузере."
    return "Не удалось открыть Spotify. Установите приложение с spotify.com."


def open_liked_songs() -> str:
    open_spotify()
    time.sleep(0.4)
    if _open_uri("spotify:collection:tracks"):
        return "Открываю вашу медиатеку — любимые треки."
    if _open_uri("https://open.spotify.com/collection/tracks"):
        return "Открываю любимые треки в браузере."
    return "Не удалось открыть медиатеку Spotify."


def open_library() -> str:
    open_spotify()
    time.sleep(0.4)
    if _open_uri("spotify:app:collection"):
        return "Открываю вашу медиатеку Spotify."
    return open_liked_songs()


def _press_enter(times: int = 1, delay: float = 1.2) -> None:
    """Best-effort: after search opens, Enter often starts the first result."""
    if SYSTEM != "Windows":
        return

    def _worker() -> None:
        time.sleep(delay)
        try:
            import ctypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            KEYEVENTF_KEYUP = 0x0002
            VK_RETURN = 0x0D
            for _ in range(max(1, times)):
                user32.keybd_event(VK_RETURN, 0, 0, 0)
                user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.35)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def _api_configured() -> bool:
    return bool(
        os.getenv("SPOTIFY_CLIENT_ID")
        and os.getenv("SPOTIFY_CLIENT_SECRET")
        and os.getenv("SPOTIFY_REFRESH_TOKEN")
    )


def _get_access_token() -> str | None:
    now = time.time()
    cached = _TOKEN_CACHE.get("access")
    expires = float(_TOKEN_CACHE.get("expires") or 0)
    if cached and now < expires - 30:
        return str(cached)

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    refresh = os.getenv("SPOTIFY_REFRESH_TOKEN", "")
    if not (client_id and client_secret and refresh):
        return None

    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    token = payload.get("access_token")
    if not token:
        return None
    _TOKEN_CACHE["access"] = token
    _TOKEN_CACHE["expires"] = now + float(payload.get("expires_in", 3600))
    return str(token)


def _api_request(method: str, url: str, body: dict | None = None) -> dict | list | None:
    token = _get_access_token()
    if not token:
        return None
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode())
    except urllib.error.HTTPError as exc:
        # 404 player = no active device — caller can fall back to URI
        if exc.code in {404, 403}:
            return None
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def search_track(query: str) -> dict | None:
    """Return first track dict from Spotify search API, or None."""
    q = (query or "").strip()
    if not q or not _api_configured():
        return None
    url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
        {"q": q, "type": "track", "limit": 1, "market": "from_token"}
    )
    payload = _api_request("GET", url)
    if not isinstance(payload, dict):
        return None
    items = (((payload.get("tracks") or {}).get("items")) or [])
    return items[0] if items else None


def search_library(query: str) -> dict | None:
    """Search user's saved tracks (media library) for a fuzzy name match."""
    q = (query or "").strip().lower()
    if not q or not _api_configured():
        return None
    url = "https://api.spotify.com/v1/me/tracks?" + urllib.parse.urlencode(
        {"limit": 50, "market": "from_token"}
    )
    payload = _api_request("GET", url)
    if not isinstance(payload, dict):
        return None
    best = None
    for item in payload.get("items") or []:
        track = item.get("track") or {}
        name = str(track.get("name") or "").lower()
        artists = " ".join(a.get("name", "") for a in (track.get("artists") or [])).lower()
        hay = f"{name} {artists}"
        if q in hay or all(part in hay for part in q.split() if len(part) > 1):
            best = track
            break
    return best


def _play_uris(uris: list[str]) -> bool:
    result = _api_request("PUT", "https://api.spotify.com/v1/me/player/play", {"uris": uris})
    return result is not None


def _track_label(track: dict) -> str:
    name = track.get("name") or "трек"
    artists = ", ".join(a.get("name", "") for a in (track.get("artists") or []) if a.get("name"))
    return f"{name} — {artists}" if artists else str(name)


def play_song(query: str, *, prefer_library: bool = False) -> str:
    """Open Spotify and play/search for a song.

    With API credentials: searches library (optional) then catalog, then starts playback.
    Without API: opens Spotify search for the query and tries to start the first result.
    """
    q = (query or "").strip()
    if not q:
        return open_spotify()

    open_spotify()
    time.sleep(0.5)

    track = None
    if _api_configured():
        if prefer_library:
            track = search_library(q) or search_track(q)
        else:
            track = search_track(q) or search_library(q)

    if track:
        uri = track.get("uri") or (f"spotify:track:{track['id']}" if track.get("id") else None)
        label = _track_label(track)
        if uri and _play_uris([uri]):
            return f"Включаю в Spotify: {label}."
        if uri and _open_uri(str(uri)):
            _press_enter(times=1, delay=1.5)
            return f"Открываю в Spotify: {label}."

    # URI search fallback — works without developer tokens
    encoded = urllib.parse.quote(q)
    if _open_uri(f"spotify:search:{encoded}"):
        _press_enter(times=2, delay=1.6)
        return f"Ищу в Spotify «{q}» и запускаю."
    web = "https://open.spotify.com/search/" + urllib.parse.quote(q)
    if _open_uri(web):
        return f"Открываю поиск Spotify в браузере: {q}."
    return f"Не удалось открыть Spotify для «{q}»."


def play_from_library(query: str) -> str:
    return play_song(query, prefer_library=True)
