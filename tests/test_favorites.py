"""Tests for Discord / Chrome / games / Cursor / Word command routing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import memory
from jarvis import reminders
from jarvis.commands import parse_and_run


class FavoritesCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self._patchers = [
            mock.patch.object(memory, "DATA_DIR", root),
            mock.patch.object(memory, "SETTINGS_FILE", root / "settings.json"),
            mock.patch.object(memory, "NOTES_FILE", root / "notes.json"),
            mock.patch.object(memory, "HISTORY_FILE", root / "history.json"),
        ]
        for patcher in self._patchers:
            patcher.start()
        reminders.clear_reminders()

    def tearDown(self) -> None:
        reminders.clear_reminders()
        for patcher in self._patchers:
            patcher.stop()
        self._tmp.cleanup()

    @mock.patch("jarvis.actions.discord_app.open_discord", return_value="Открываю Discord.")
    def test_discord_open(self, mocked) -> None:
        result = parse_and_run("открой дискорд")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.discord_app.toggle_mute", return_value="mute")
    def test_discord_mute(self, mocked) -> None:
        result = parse_and_run("мют дискорд")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.games.launch_cs2", return_value="CS2")
    def test_launch_cs2(self, mocked) -> None:
        result = parse_and_run("запусти кс2")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.games.launch_pubg", return_value="PUBG")
    def test_launch_pubg(self, mocked) -> None:
        result = parse_and_run("запусти пабг")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.games.game_mode", return_value="game mode")
    def test_game_mode_cs(self, mocked) -> None:
        result = parse_and_run("игровой режим кс")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("кс")

    @mock.patch("jarvis.actions.games.game_mode", return_value="game mode pubg")
    def test_go_pubg_uses_game_mode(self, mocked) -> None:
        result = parse_and_run("го в пабг")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("пабг")

    @mock.patch("jarvis.actions.cursor_app.open_cursor", return_value="Cursor")
    def test_cursor_open(self, mocked) -> None:
        result = parse_and_run("открой курсор")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with(None)

    @mock.patch("jarvis.actions.cursor_app.open_cursor", return_value="Cursor projects")
    def test_cursor_open_path(self, mocked) -> None:
        result = parse_and_run("открой курсор проекты")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("проекты")

    @mock.patch("jarvis.actions.word_app.open_word", return_value="Word")
    def test_word_open(self, mocked) -> None:
        result = parse_and_run("открой ворд")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with(None)

    @mock.patch("jarvis.actions.word_app.new_document", return_value="new doc")
    def test_word_new(self, mocked) -> None:
        result = parse_and_run("новый документ")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.chrome_app.new_tab", return_value="tab")
    def test_chrome_new_tab(self, mocked) -> None:
        result = parse_and_run("новая вкладка")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with(None)

    @mock.patch("jarvis.actions.chrome_app.incognito", return_value="incognito")
    def test_chrome_incognito(self, mocked) -> None:
        result = parse_and_run("инкогнито")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with(None)

    @mock.patch("jarvis.actions.workflows.work_mode", return_value="work")
    def test_work_mode(self, mocked) -> None:
        result = parse_and_run("рабочий режим")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    def test_stack(self) -> None:
        result = parse_and_run("мой стек")
        self.assertTrue(result.ok)
        self.assertIn("Discord", result.spoken)
        self.assertIn("CS2", result.spoken)


if __name__ == "__main__":
    unittest.main()
