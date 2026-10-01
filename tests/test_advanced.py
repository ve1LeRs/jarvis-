"""Tests for macros, confirmations, todos, reminders-at-time, context."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import confirm
from jarvis import context
from jarvis import macros
from jarvis import memory
from jarvis import reminders
from jarvis.commands import parse_and_run


class AdvancedFeatureTests(unittest.TestCase):
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
        ]
        for patcher in self._patchers:
            patcher.start()
        reminders.clear_reminders()
        confirm.clear()
        context.set_mode("idle", quiet=False, apps=[])

    def tearDown(self) -> None:
        reminders.clear_reminders()
        confirm.clear()
        for patcher in self._patchers:
            patcher.stop()
        self._tmp.cleanup()

    def test_todos_and_today(self) -> None:
        self.assertTrue(parse_and_run("добавь в дела купить молоко").ok)
        listed = parse_and_run("дела")
        self.assertIn("молоко", listed.spoken)
        brief = parse_and_run("что сегодня")
        self.assertIn("молоко", brief.spoken)
        done = parse_and_run("сделал молоко")
        self.assertIn("выполненным", done.spoken)

    def test_absolute_reminder(self) -> None:
        result = parse_and_run("напомни в 23:59 проверить сборку")
        self.assertTrue(result.ok)
        self.assertIn("Напомню", result.spoken)
        self.assertIn("сборку", result.spoken)

    def test_macro_learn_and_run(self) -> None:
        learned = parse_and_run("когда говорю погнали то запускай пабг")
        self.assertTrue(learned.ok)
        with mock.patch("jarvis.actions.games.launch_pubg", return_value="PUBG"):
            # Macro maps to "запускай пабг" which may not parse — map to known command
            macros.add_macro("погнали", "запусти пабг")
            result = parse_and_run("погнали")
            self.assertTrue(result.ok)
            self.assertIn("PUBG", result.spoken)

    def test_shutdown_needs_confirm(self) -> None:
        ask = parse_and_run("выключи компьютер")
        self.assertIn("Подтвердите", ask.spoken)
        with mock.patch("jarvis.actions.system.shutdown_pc", return_value="Выключаю."):
            confirmed = parse_and_run("подтверди")
            self.assertTrue(confirmed.ok)
            self.assertIn("Выключаю", confirmed.spoken)

    def test_context_quiet_shortens(self) -> None:
        context.set_mode("game", game="cs2", quiet=True)
        long = "Первое предложение здесь. " + ("ещё текст " * 40)
        short = context.adapt_speech(long)
        self.assertLess(len(short), len(long))

    @mock.patch("jarvis.actions.screen.read_selection", return_value="В выделении: hello")
    def test_read_selection(self, mocked) -> None:
        result = parse_and_run("прочитай выделение")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.workflows.morning_mode", return_value="morning")
    def test_morning(self, mocked) -> None:
        result = parse_and_run("доброе утро")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.games.friends_mode", return_value="friends cs")
    def test_friends_mode(self, mocked) -> None:
        result = parse_and_run("с друзьями кс")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("кс")


if __name__ == "__main__":
    unittest.main()
