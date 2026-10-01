"""Phone bridge: Telegram bot + local HTTP webhook (WhatsApp gateways / Shortcuts).

Telegram:
  set TELEGRAM_BOT_TOKEN or «сохрани телеграм токен <token>»
  optional TELEGRAM_CHAT_IDS=123,456 (comma-separated allowlist)
  «включи телеграм мост»

HTTP / WhatsApp-compatible webhook (localhost):
  POST http://127.0.0.1:8765/command  {"text":"открой дискорд","secret":"..."}
  WhatsApp Cloud API style:
    GET  /whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
    POST /whatsapp  (Meta webhook payload) — replies via Graph API if token set

Secrets live in ~/.jarvis/bridge.json
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from jarvis import memory

BRIDGE_FILE = memory.DATA_DIR / "bridge.json"
DEFAULT_PORT = int(os.getenv("JARVIS_BRIDGE_PORT", "8765"))

CommandHandler = Callable[[str], str]

_lock = threading.RLock()
_handler: CommandHandler | None = None
_tg_thread: threading.Thread | None = None
_http_thread: threading.Thread | None = None
_tg_stop = threading.Event()
_http_server: ThreadingHTTPServer | None = None
_state = {
    "telegram_running": False,
    "http_running": False,
    "last_error": "",
    "last_from": "",
}


def set_command_handler(fn: CommandHandler) -> None:
    global _handler
    _handler = fn


def _load() -> dict[str, Any]:
    data = memory._read_json(BRIDGE_FILE, {})  # noqa: SLF001
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, Any]) -> None:
    memory._write_json(BRIDGE_FILE, data)  # noqa: SLF001


def _cfg() -> dict[str, Any]:
    data = _load()
    # Env overrides
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        data["telegram_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("TELEGRAM_CHAT_IDS"):
        data["telegram_chat_ids"] = [
            x.strip() for x in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if x.strip()
        ]
    if os.getenv("JARVIS_BRIDGE_SECRET"):
        data["http_secret"] = os.getenv("JARVIS_BRIDGE_SECRET")
    if os.getenv("WHATSAPP_VERIFY_TOKEN"):
        data["whatsapp_verify_token"] = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if os.getenv("WHATSAPP_TOKEN"):
        data["whatsapp_token"] = os.getenv("WHATSAPP_TOKEN")
    if os.getenv("WHATSAPP_PHONE_NUMBER_ID"):
        data["whatsapp_phone_number_id"] = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    data.setdefault("port", DEFAULT_PORT)
    data.setdefault("telegram_chat_ids", [])
    data.setdefault("http_secret", "")
    data.setdefault("whatsapp_verify_token", "jarvis")
    return data


def save_telegram_token(token: str) -> str:
    token = (token or "").strip()
    if not token or len(token) < 20:
        return "Нужен токен от @BotFather, например: 123456:ABC..."
    data = _load()
    data["telegram_token"] = token
    _save(data)
    return "Токен Telegram сохранён. Скажите «включи телеграм мост»."


def allow_telegram_chat(chat_id: str) -> str:
    chat_id = (chat_id or "").strip()
    if not chat_id:
        return "Укажите chat id."
    data = _load()
    ids = list(data.get("telegram_chat_ids") or [])
    if chat_id not in ids:
        ids.append(chat_id)
    data["telegram_chat_ids"] = ids
    _save(data)
    return f"Разрешил Telegram chat {chat_id}."


def save_http_secret(secret: str) -> str:
    secret = (secret or "").strip()
    if not secret:
        return "Нужен секрет для HTTP/WhatsApp моста."
    data = _load()
    data["http_secret"] = secret
    _save(data)
    return "Секрет моста сохранён."


def save_whatsapp_cloud(
    token: str,
    phone_number_id: str,
    *,
    verify_token: str = "jarvis",
) -> str:
    token = (token or "").strip()
    phone_number_id = (phone_number_id or "").strip()
    if not token or not phone_number_id:
        return "Нужны WhatsApp token и phone_number_id из Meta Cloud API."
    data = _load()
    data["whatsapp_token"] = token
    data["whatsapp_phone_number_id"] = phone_number_id
    data["whatsapp_verify_token"] = (verify_token or "jarvis").strip()
    _save(data)
    return (
        "WhatsApp Cloud API сохранён. Поднимите туннель на порт моста и "
        "укажите webhook …/whatsapp в Meta."
    )


def _run_command(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Пустая команда."
    # Strip bot mention / wake
    low = text.lower()
    for prefix in ("джарвис,", "джарвис ", "jarvis,", "jarvis ", "/"):
        if low.startswith(prefix):
            text = text[len(prefix) :].strip()
            low = text.lower()
            break
    if text.startswith("/start"):
        return (
            "JARVIS на связи. Пришлите команду, например: открой дискорд, "
            "что сегодня, матч кс."
        )
    if _handler is None:
        from jarvis.commands import parse_and_run

        result = parse_and_run(text)
        return result.spoken
    return _handler(text)


def _telegram_api(token: str, method: str, payload: dict | None = None) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if data else "GET",
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError) as exc:
        with _lock:
            _state["last_error"] = str(exc)
        return None


def _telegram_allowed(chat_id: str | int, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    return str(chat_id) in {str(x) for x in allowlist}


def _telegram_loop() -> None:
    cfg = _cfg()
    token = str(cfg.get("telegram_token") or "")
    allowlist = list(cfg.get("telegram_chat_ids") or [])
    offset = 0
    with _lock:
        _state["telegram_running"] = True
        _state["last_error"] = ""
    while not _tg_stop.is_set():
        payload = _telegram_api(
            token,
            "getUpdates",
            {"timeout": 25, "offset": offset, "allowed_updates": ["message"]},
        )
        if not payload or not payload.get("ok"):
            _tg_stop.wait(3)
            continue
        for update in payload.get("result") or []:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            text = message.get("text") or message.get("caption") or ""
            if chat_id is None or not text:
                continue
            if not _telegram_allowed(chat_id, allowlist):
                _telegram_api(
                    token,
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": "Этот чат не в allowlist. Скажите Jarvis: "
                        f"разреши телеграм чат {chat_id}",
                    },
                )
                continue
            with _lock:
                _state["last_from"] = f"telegram:{chat_id}"
            reply = _run_command(text)
            _telegram_api(token, "sendMessage", {"chat_id": chat_id, "text": reply[:3500]})
    with _lock:
        _state["telegram_running"] = False


def start_telegram() -> str:
    global _tg_thread
    cfg = _cfg()
    if not cfg.get("telegram_token"):
        return (
            "Нет токена. Создайте бота у @BotFather, затем "
            "«сохрани телеграм токен <token>» или TELEGRAM_BOT_TOKEN."
        )
    if _tg_thread and _tg_thread.is_alive():
        return "Telegram мост уже работает."
    _tg_stop.clear()
    _tg_thread = threading.Thread(target=_telegram_loop, daemon=True, name="jarvis-tg")
    _tg_thread.start()
    return "Telegram мост включён. Пишите боту команды с телефона."


def stop_telegram() -> str:
    _tg_stop.set()
    return "Telegram мост выключается."


def _whatsapp_send(to: str, text: str) -> None:
    cfg = _cfg()
    token = cfg.get("whatsapp_token")
    phone_id = cfg.get("whatsapp_phone_number_id")
    if not token or not phone_id or not to:
        return
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:3500]},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _state["last_error"] = f"whatsapp send: {exc}"


class _BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # noqa: ANN002
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _write(self, code: int, payload: dict | str, *, ctype: str = "application/json") -> None:
        if isinstance(payload, dict):
            body = json.dumps(payload, ensure_ascii=False).encode()
        else:
            body = str(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/status"}:
            self._write(200, status())
            return
        if parsed.path == "/whatsapp":
            qs = urllib.parse.parse_qs(parsed.query)
            mode = (qs.get("hub.mode") or [""])[0]
            token = (qs.get("hub.verify_token") or [""])[0]
            challenge = (qs.get("hub.challenge") or [""])[0]
            expected = str(_cfg().get("whatsapp_verify_token") or "jarvis")
            if mode == "subscribe" and token == expected:
                self._write(200, challenge, ctype="text/plain")
                return
            self._write(403, {"ok": False, "error": "verify failed"})
            return
        self._write(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        cfg = _cfg()
        secret = str(cfg.get("http_secret") or "")

        if parsed.path in {"/command", "/jarvis"}:
            data = self._read_json()
            if secret and data.get("secret") != secret:
                header_secret = self.headers.get("X-Jarvis-Secret") or ""
                if header_secret != secret:
                    self._write(401, {"ok": False, "error": "bad secret"})
                    return
            text = str(data.get("text") or data.get("command") or data.get("message") or "")
            with _lock:
                _state["last_from"] = "http:/command"
            reply = _run_command(text)
            self._write(200, {"ok": True, "reply": reply})
            return

        if parsed.path == "/whatsapp":
            data = self._read_json()
            # Generic gateway: {"text":"...", "from":"...", "secret":"..."}
            if data.get("text") and (not secret or data.get("secret") == secret):
                with _lock:
                    _state["last_from"] = f"whatsapp:{data.get('from') or '?'}"
                reply = _run_command(str(data.get("text")))
                to = str(data.get("from") or "")
                if to and cfg.get("whatsapp_token"):
                    _whatsapp_send(to, reply)
                self._write(200, {"ok": True, "reply": reply})
                return
            # Meta Cloud API webhook shape
            try:
                entry = (data.get("entry") or [])[0]
                changes = (entry.get("changes") or [])[0]
                value = changes.get("value") or {}
                messages = value.get("messages") or []
                if not messages:
                    self._write(200, {"ok": True})
                    return
                msg = messages[0]
                text = ((msg.get("text") or {}).get("body")) or ""
                sender = msg.get("from") or ""
                with _lock:
                    _state["last_from"] = f"whatsapp:{sender}"
                reply = _run_command(text)
                _whatsapp_send(sender, reply)
            except Exception as exc:  # noqa: BLE001
                with _lock:
                    _state["last_error"] = str(exc)
            self._write(200, {"ok": True})
            return

        self._write(404, {"ok": False, "error": "not found"})


def start_http() -> str:
    global _http_thread, _http_server
    if _http_server is not None:
        return f"HTTP мост уже на порту {_cfg().get('port', DEFAULT_PORT)}."
    port = int(_cfg().get("port") or DEFAULT_PORT)

    def _serve() -> None:
        global _http_server
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), _BridgeHandler)
        except OSError as exc:
            with _lock:
                _state["last_error"] = str(exc)
                _state["http_running"] = False
            return
        _http_server = server
        with _lock:
            _state["http_running"] = True
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            with _lock:
                _state["http_running"] = False

    _http_thread = threading.Thread(target=_serve, daemon=True, name="jarvis-http-bridge")
    _http_thread.start()
    time.sleep(0.15)
    with _lock:
        running = bool(_state["http_running"])
        err = _state.get("last_error") or ""
    if not running and err:
        return f"Не удалось открыть порт {port}: {err}"
    secret_hint = "с секретом" if _cfg().get("http_secret") else "без секрета (задайте «секрет моста …»)"
    return (
        f"HTTP мост на порту {port} ({secret_hint}). "
        f"POST /command или WhatsApp webhook /whatsapp."
    )


def stop_http() -> str:
    global _http_server
    server = _http_server
    _http_server = None
    if server is not None:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
    return "HTTP мост остановлен."


def start_all() -> str:
    parts = [start_http()]
    cfg = _cfg()
    if cfg.get("telegram_token"):
        parts.append(start_telegram())
    return " ".join(parts)


def stop_all() -> str:
    return " ".join([stop_telegram(), stop_http()])


def status() -> dict[str, Any]:
    cfg = _cfg()
    with _lock:
        return {
            "telegram_configured": bool(cfg.get("telegram_token")),
            "telegram_running": bool(_state["telegram_running"]),
            "http_running": bool(_state["http_running"]),
            "port": int(cfg.get("port") or DEFAULT_PORT),
            "whatsapp_configured": bool(cfg.get("whatsapp_token") and cfg.get("whatsapp_phone_number_id")),
            "has_http_secret": bool(cfg.get("http_secret")),
            "last_from": _state.get("last_from") or "",
            "last_error": _state.get("last_error") or "",
            "allowlist": list(cfg.get("telegram_chat_ids") or []),
        }


def status_text() -> str:
    s = status()
    parts = [
        f"Telegram: {'он' if s['telegram_running'] else 'выкл'}"
        + (" (токен есть)" if s["telegram_configured"] else " (нет токена)"),
        f"HTTP:{s['port']} {'он' if s['http_running'] else 'выкл'}",
    ]
    if s["whatsapp_configured"]:
        parts.append("WhatsApp Cloud настроен")
    if s["last_from"]:
        parts.append(f"последний: {s['last_from']}")
    if s["last_error"]:
        parts.append(f"ошибка: {s['last_error']}")
    return "Мост: " + "; ".join(parts) + "."


def autostart_if_configured() -> None:
    """Called on Jarvis boot — start bridges when tokens already saved."""
    cfg = _cfg()
    if cfg.get("telegram_token") or cfg.get("autostart"):
        try:
            start_all()
        except Exception:
            pass
