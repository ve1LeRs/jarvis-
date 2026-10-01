"""Tests for calendar, plugins, paths, game match, OCR click routing, proactive."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import confirm
from jarvis import context
from jarvis import macros
from jarvis import memory
from jarvis import plugins
from jarvis import proactive
from jarvis.actions import calendar as cal
from jarvis.commands import parse_and_run
from jarvis import paths


class NextWaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self._patchers = [
            mock.patch.object(memory, "DATA_DIR", root),
            mock.patch.object(memory, "SETTINGS_FILE", root / "settings.json"),
            mock.patch.object(memory, "NOTES_FILE", root / "notes.json"),
            mock.patch.object(memory, "HISTORY_FILE", root / "history.json"),
            mock.patch.object(memory, "TODOS_FILE", root / "todos.json"),
            mock.patch.object(macros, "MACROS_FILE", root / "macros.json"),
            mock.patch.object(cal, "CALENDAR_FILE", root / "calendar.json"),
            mock.patch.object(plugins, "PLUGINS_DIR", root / "plugins"),
            mock.patch.object(paths, "PATHS_KEY", "app_paths"),
        ]
        for patcher in self._patchers:
            patcher.start()
        confirm.clear()
        context.set_mode("idle", quiet=False, apps=[])
        proactive.enable(True)

    def tearDown(self) -> None:
        confirm.clear()
        for patcher in self._patchers:
            patcher.stop()
        self._tmp.cleanup()

    def test_parse_ics_and_today(self) -> None:
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Standup
DTSTART:20261001T100000
DTEND:20261001T103000
END:VEVENT
BEGIN:VEVENT
SUMMARY:Demo
DTSTART:20261001T180000
END:VEVENT
END:VCALENDAR
"""
        events = cal.parse_ics(ics)
        self.assertEqual(len(events), 2)
        with mock.patch.object(cal, "date") as date_mod:
            # force "today" via events_for_day by writing cache
            pass
        data = {"feeds": ["https://example.com/cal.ics"], "cache": events}
        cal._save(data)
        with mock.patch("jarvis.actions.calendar.date") as d:
            from datetime import date as real_date

            d.today.return_value = real_date(2026, 10, 1)
            text = cal.today_events_text()
        self.assertIn("Standup", text)
        self.assertIn("Demo", text)

    def test_calendar_command_add_rejects_bad_url(self) -> None:
        result = parse_and_run("добавь календарь not-a-url")
        self.assertTrue(result.ok)
        self.assertIn("ICS", result.spoken)

    def test_plugin_load_and_run(self) -> None:
        plugins.ensure_dir()
        plugin_path = plugins.PLUGINS_DIR / "demo.py"
        plugin_path.write_text(
            "NAME = 'demo'\n"
            "RULES = [(r'^пинг$', 'plugin_ping')]\n"
            "def handle_plugin_ping(payload, raw):\n"
            "    return 'Понг из плагина.'\n",
            encoding="utf-8",
        )
        reloaded = parse_and_run("перезагрузи плагины")
        self.assertIn("1", reloaded.spoken)
        result = parse_and_run("пинг")
        self.assertTrue(result.ok)
        self.assertIn("Понг", result.spoken)

    def test_paths_detect(self) -> None:
        with mock.patch.object(paths, "detect_all", return_value={"chrome": "/bin/chrome"}):
            result = parse_and_run("найди программы")
        self.assertTrue(result.ok)
        self.assertIn("1", result.spoken)

    def test_match_and_exit_game(self) -> None:
        with mock.patch("jarvis.actions.games.launch_cs2", return_value="CS2"), mock.patch(
            "jarvis.actions.discord_app.open_discord", return_value="Discord"
        ), mock.patch(
            "jarvis.actions.discord_app.toggle_deafen", return_value="Deafen"
        ), mock.patch(
            "jarvis.actions.games._pause_spotify_soft"
        ):
            started = parse_and_run("матч кс")
            self.assertTrue(started.ok)
            self.assertIn("Матч", started.spoken)
            ended = parse_and_run("выйди из игры")
            self.assertTrue(ended.ok)
            self.assertIn("игрового", ended.spoken)

    def test_click_text_routing(self) -> None:
        with mock.patch("jarvis.actions.screen.click_text", return_value="Нажимаю «OK»") as mocked:
            result = parse_and_run("нажми кнопку OK")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("ok")

    def test_discord_voice_remember(self) -> None:
        result = parse_and_run("запомни войс канал общий")
        self.assertTrue(result.ok)
        self.assertIn("общий", result.spoken)
        with mock.patch(
            "jarvis.actions.discord_app.join_voice_channel", return_value="joining"
        ) as mocked:
            again = parse_and_run("зайди в войс")
        self.assertTrue(again.ok)
        mocked.assert_called()

    def test_spotify_keys_save(self) -> None:
        with mock.patch.object(
            memory, "DATA_DIR", Path(self._tmp.name)
        ), mock.patch(
            "jarvis.actions.spotify.SPOTIFY_AUTH_FILE", Path(self._tmp.name) / "spotify.json"
        ):
            result = parse_and_run("сохрани спотифай ключи abc123 secret999")
        self.assertTrue(result.ok)
        self.assertIn("сохранены", result.spoken.lower())

    def test_proactive_toggle(self) -> None:
        off = parse_and_run("проактивность выкл")
        self.assertIn("выключена", off.spoken.lower())
        on = parse_and_run("проактивность вкл")
        self.assertIn("включена", on.spoken.lower())

    def test_morning_brief_includes_calendar_hook(self) -> None:
        parse_and_run("добавь в дела тест")
        brief = proactive.build_morning_brief()
        self.assertIn("тест", brief)


if __name__ == "__main__":
    unittest.main()
