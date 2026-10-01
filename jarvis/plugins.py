"""Load user plugins from ~/.jarvis/plugins/*.py

Each plugin may define:
  RULES: list[tuple[pattern_str, action_name]]
  HANDLERS: dict[str, callable[[payload:str, raw:str], str | tuple[bool,str]]]
  NAME: optional display name
"""

from __future__ import annotations

import importlib.util
import re
import threading
from pathlib import Path
from typing import Any, Callable

from jarvis import memory

PLUGINS_DIR = memory.DATA_DIR / "plugins"

_lock = threading.RLock()
_loaded: list[dict[str, Any]] = []


Handler = Callable[[str, str], Any]


def ensure_dir() -> Path:
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    readme = PLUGINS_DIR / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Положите сюда .py плагины.\n"
            "Пример:\n"
            "NAME = 'demo'\n"
            "RULES = [(r'^пинг$', 'plugin_ping')]\n"
            "def handle_plugin_ping(payload, raw):\n"
            "    return 'Понг из плагина.'\n"
            "# или HANDLERS = {'plugin_ping': handle_plugin_ping}\n",
            encoding="utf-8",
        )
    return PLUGINS_DIR


def reload() -> str:
    with _lock:
        _loaded.clear()
        ensure_dir()
        count = 0
        for path in sorted(PLUGINS_DIR.glob("*.py")):
            if path.name.startswith("_"):
                continue
            mod = _import_path(path)
            if mod is None:
                continue
            rules_raw = getattr(mod, "RULES", None) or []
            handlers: dict[str, Handler] = dict(getattr(mod, "HANDLERS", {}) or {})
            # Auto-bind handle_<action> functions
            for name in dir(mod):
                if name.startswith("handle_") and callable(getattr(mod, name)):
                    action = name[len("handle_") :]
                    handlers.setdefault(action, getattr(mod, name))
            compiled = []
            for item in rules_raw:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                pattern, action = item
                try:
                    compiled.append((re.compile(str(pattern), re.I), str(action)))
                except re.error:
                    continue
            _loaded.append(
                {
                    "name": getattr(mod, "NAME", path.stem),
                    "path": str(path),
                    "rules": compiled,
                    "handlers": handlers,
                }
            )
            count += 1
        return f"Загружено плагинов: {count}."


def _import_path(path: Path):
    try:
        spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def list_plugins() -> str:
    with _lock:
        if not _loaded:
            reload()
        if not _loaded:
            return f"Плагинов нет. Папка: {ensure_dir()}"
        names = [str(p.get("name")) for p in _loaded]
        return "Плагины: " + ", ".join(names) + "."


def match_and_run(text: str) -> tuple[bool, str] | None:
    """Try plugin rules. Returns (ok, spoken) or None if no match."""
    with _lock:
        if not _loaded:
            reload()
        plugins = list(_loaded)
    for plugin in plugins:
        for pattern, action in plugin.get("rules") or []:
            m = pattern.match(text)
            if not m:
                continue
            payload = (m.group(1) if m.lastindex else "") or ""
            handler = (plugin.get("handlers") or {}).get(action)
            if not handler:
                return False, f"Плагин «{plugin.get('name')}»: нет обработчика {action}."
            try:
                result = handler(payload.strip(), text)
            except Exception as exc:  # noqa: BLE001
                return False, f"Ошибка плагина «{plugin.get('name')}»: {exc}"
            if isinstance(result, tuple) and len(result) >= 2:
                return bool(result[0]), str(result[1])
            return True, str(result)
    return None
