"""Spotify control: open app, search/play tracks, liked songs, OAuth wizard.

Works out of the box via Spotify desktop URIs on Windows.
Optional Web API via env vars or ~/.jarvis/spotify.json (OAuth wizard):

  SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET / SPOTIFY_REFRESH_TOKEN
  or voice: «настрой спотифай» / «spotify login»
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
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jarvis import memory

SYSTEM = platform.system()

_TOKEN_CACHE: dict[str, object] = {"access": None, "expires": 0.0}
SPOTIFY_AUTH_FILE = memory.DATA_DIR / "spotify.json"
_REDIRECT_PORT = 8732
_REDIRECT_URI = f"http://127.0.0.1:{_REDIRECT_PORT}/callback"
_SCOPES = (
    "user-modify-playback-state user-read-playback-state "
    "user-library-read playlist-read-private user-read-currently-playing"
)


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


def open_playlist(name: str) -> str:
    """Search playlists by name and open the first match (URI search)."""
    q = (name or "").strip()
    if not q:
        return open_spotify()
    open_spotify()
    time.sleep(0.4)
    encoded = urllib.parse.quote(f"playlist:{q}")
    if _open_uri(f"spotify:search:{encoded}"):
        _press_enter(times=2, delay=1.6)
        return f"Ищу плейлист «{q}» в Spotify."
    return play_song(q)


def open_radio_or_wave() -> str:
    """Best-effort open Spotify Radio / Home mix."""
    open_spotify()
    time.sleep(0.5)
    # Home / made-for-you style landing
    if _open_uri("spotify:app:home"):
        return "Открываю главную Spotify — там волны и миксы."
    if _open_uri("https://open.spotify.com"):
        return "Открываю Spotify Home."
    return open_spotify()


def focus_spotify_volume(direction: str) -> str:
    """Change system volume after focusing Spotify (best-effort 'spotify volume')."""
    from jarvis.actions import system as sys_act
    from jarvis.actions import launch as launch_mod

    open_spotify()
    time.sleep(0.4)
    launch_mod.focus_window(["spotify"])
    if direction in {"up", "громче"}:
        return "Громкость Spotify выше. " + sys_act.volume_up()
    if direction in {"down", "тише"}:
        return "Громкость Spotify ниже. " + sys_act.volume_down()
    return sys_act.volume_mute()



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


def _load_auth() -> dict:
    data = memory._read_json(SPOTIFY_AUTH_FILE, {})  # noqa: SLF001
    return data if isinstance(data, dict) else {}


def _save_auth(data: dict) -> None:
    memory._write_json(SPOTIFY_AUTH_FILE, data)  # noqa: SLF001


def _creds() -> tuple[str, str, str]:
    auth = _load_auth()
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or str(auth.get("client_id") or "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or str(auth.get("client_secret") or "")
    refresh = os.getenv("SPOTIFY_REFRESH_TOKEN") or str(auth.get("refresh_token") or "")
    return client_id, client_secret, refresh


def _api_configured() -> bool:
    client_id, client_secret, refresh = _creds()
    return bool(client_id and client_secret and refresh)


def _get_access_token() -> str | None:
    now = time.time()
    cached = _TOKEN_CACHE.get("access")
    expires = float(_TOKEN_CACHE.get("expires") or 0)
    if cached and now < expires - 30:
        return str(cached)

    client_id, client_secret, refresh = _creds()
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
    # Persist rotated refresh token if Spotify issued one
    new_refresh = payload.get("refresh_token")
    if new_refresh:
        auth = _load_auth()
        auth["refresh_token"] = new_refresh
        auth.setdefault("client_id", client_id)
        auth.setdefault("client_secret", client_secret)
        _save_auth(auth)
    return str(token)


def save_client_credentials(client_id: str, client_secret: str) -> str:
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if not client_id or not client_secret:
        return "Нужны client_id и client_secret из developer.spotify.com."
    auth = _load_auth()
    auth["client_id"] = client_id
    auth["client_secret"] = client_secret
    _save_auth(auth)
    return "Ключи Spotify сохранены. Скажите «войти в спотифай» для OAuth."


def start_oauth_login(*, timeout: float = 120.0) -> str:
    """Open Spotify authorize page and capture refresh token via localhost."""
    client_id, client_secret, _refresh = _creds()
    if not client_id or not client_secret:
        return (
            "Сначала сохраните ключи: в Spotify Dashboard создайте приложение, "
            f"redirect URI = {_REDIRECT_URI}, затем "
            "«сохрани спотифай ключи <id> <secret>» или задайте переменные окружения."
        )

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": _REDIRECT_URI,
            "scope": _SCOPES,
            "show_dialog": "true",
        }
    )
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(parsed.query)
            if qs.get("code"):
                result["code"] = qs["code"][0]
                body = b"<html><body><h2>JARVIS: Spotify connected. You can close this tab.</h2></body></html>"
            else:
                result["error"] = (qs.get("error") or ["unknown"])[0]
                body = b"<html><body><h2>Authorization failed.</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # noqa: ANN002
            return

    try:
        server = HTTPServer(("127.0.0.1", _REDIRECT_PORT), Handler)
    except OSError:
        return f"Порт {_REDIRECT_PORT} занят — закройте другое окно OAuth и повторите."

    server.timeout = 1.0
    _open_uri(auth_url)
    deadline = time.time() + timeout
    while time.time() < deadline and "code" not in result and "error" not in result:
        server.handle_request()
    try:
        server.server_close()
    except Exception:
        pass

    if result.get("error"):
        return f"Spotify OAuth отклонён: {result['error']}."
    code = result.get("code")
    if not code:
        return "Не дождался подтверждения в браузере. Повторите «войти в спотифай»."

    data = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT_URI,
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return "Не удалось обменять код Spotify на токен."

    refresh = payload.get("refresh_token")
    access = payload.get("access_token")
    if not refresh or not access:
        return "Spotify не вернул refresh token. Проверьте scopes приложения."
    auth = _load_auth()
    auth.update(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "connected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    )
    _save_auth(auth)
    _TOKEN_CACHE["access"] = access
    _TOKEN_CACHE["expires"] = time.time() + float(payload.get("expires_in", 3600))
    return "Spotify подключён. Можно включать треки, плейлисты и очередь голосом."


def oauth_status() -> str:
    if _api_configured():
        auth = _load_auth()
        when = auth.get("connected_at") or "через переменные окружения"
        return f"Spotify API готов ({when})."
    return (
        "Spotify API не настроен. Скажите «настрой спотифай» после создания приложения "
        f"с redirect URI {_REDIRECT_URI}."
    )


def queue_song(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return "Что добавить в очередь?"
    track = search_track(q) if _api_configured() else None
    if track and track.get("uri"):
        result = _api_request(
            "POST",
            "https://api.spotify.com/v1/me/player/queue?"
            + urllib.parse.urlencode({"uri": track["uri"]}),
        )
        if result is not None:
            return f"Добавил в очередь: {_track_label(track)}."
    return play_song(q)


def play_playlist_api(name: str) -> str:
    q = (name or "").strip()
    if not q:
        return open_spotify()
    if _api_configured():
        url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
            {"q": q, "type": "playlist", "limit": 1}
        )
        payload = _api_request("GET", url)
        if isinstance(payload, dict):
            items = (((payload.get("playlists") or {}).get("items")) or [])
            if items:
                pl = items[0]
                uri = pl.get("uri")
                label = pl.get("name") or q
                if uri:
                    result = _api_request(
                        "PUT",
                        "https://api.spotify.com/v1/me/player/play",
                        {"context_uri": uri},
                    )
                    if result is not None:
                        return f"Включаю плейлист «{label}»."
                    if _open_uri(str(uri)):
                        return f"Открываю плейлист «{label}»."
    return open_playlist(q)


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
