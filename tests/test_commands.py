"""Unit tests for command parsing (no microphone needed)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import memory
from jarvis import reminders
from jarvis.actions import fun as fun_act
from jarvis.commands import parse_and_run
from jarvis.listen import contains_wake_word, strip_wake_word


class WakeWordTests(unittest.TestCase):
    def test_wake_detected(self) -> None:
        self.assertTrue(contains_wake_word("Джарвис, открой проводник"))
        self.assertTrue(contains_wake_word("jarvis open chrome"))

    def test_strip(self) -> None:
        self.assertEqual(strip_wake_word("джарвис открой проводник"), "открой проводник")


class CommandTests(unittest.TestCase):
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

    @mock.patch("jarvis.actions.system.search_web", return_value="ok")
    def test_search_pine_beam(self, mocked) -> None:
        result = parse_and_run("найди информацию о сосновом брусе")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("сосновом брусе")

    @mock.patch("jarvis.actions.system.open_explorer", return_value="explorer")
    def test_explorer(self, mocked) -> None:
        result = parse_and_run("открой проводник")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.system.open_chrome", return_value="chrome")
    def test_chrome(self, mocked) -> None:
        result = parse_and_run("открой хром")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.system.open_url", return_value="yt")
    def test_youtube(self, mocked) -> None:
        result = parse_and_run("открой ютуб")
        self.assertTrue(result.ok)

    def test_time(self) -> None:
        result = parse_and_run("который час")
        self.assertTrue(result.ok)
        self.assertIn("Сейчас", result.spoken)

    def test_date_has_weekday(self) -> None:
        result = parse_and_run("какая дата")
        self.assertTrue(result.ok)
        self.assertIn("года", result.spoken)

    def test_help(self) -> None:
        result = parse_and_run("помощь")
        self.assertTrue(result.ok)
        self.assertIn("напоминан", result.spoken.lower())

    @mock.patch("jarvis.autostart.enable_autostart", return_value="enabled")
    def test_autostart_on(self, mocked) -> None:
        result = parse_and_run("включи автозапуск")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    def test_unknown(self) -> None:
        result = parse_and_run("блаблабла xyz")
        self.assertFalse(result.ok)

    def test_notes(self) -> None:
        add = parse_and_run("запиши купить молоко")
        self.assertTrue(add.ok)
        listed = parse_and_run("заметки")
        self.assertIn("молоко", listed.spoken)

    def test_reminder_parse_and_schedule(self) -> None:
        result = parse_and_run("через 5 минут проверить духовку")
        self.assertTrue(result.ok)
        self.assertIn("Напомню", result.spoken)
        listed = parse_and_run("напоминания")
        self.assertIn("духовку", listed.spoken)

    def test_calculate(self) -> None:
        result = parse_and_run("посчитай 12 + 30")
        self.assertTrue(result.ok)
        self.assertIn("42", result.spoken)

    def test_coin_and_joke(self) -> None:
        coin = parse_and_run("монетка")
        self.assertTrue(coin.ok)
        joke = parse_and_run("анекдот")
        self.assertTrue(joke.ok)

    @mock.patch("jarvis.actions.system.volume_up", return_value="Громкость выше.")
    def test_volume(self, mocked) -> None:
        result = parse_and_run("громче")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.system.open_weather", return_value="weather")
    def test_weather(self, mocked) -> None:
        result = parse_and_run("погода в москве")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("москве")

    @mock.patch("jarvis.actions.system.search_youtube", return_value="yt")
    def test_youtube_search(self, mocked) -> None:
        result = parse_and_run("найди на ютубе lofti")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("lofti")

    def test_mute_and_repeat(self) -> None:
        parse_and_run("который час")
        muted = parse_and_run("молчи")
        self.assertTrue(muted.ok)
        self.assertTrue(memory.is_muted())
        unmuted = parse_and_run("говори")
        self.assertTrue(unmuted.ok)
        self.assertFalse(memory.is_muted())
        with mock.patch("jarvis.actions.system.tell_time", return_value="Сейчас 12:00.") as mocked:
            again = parse_and_run("повтори")
            self.assertTrue(again.ok)
            mocked.assert_called_once()

    def test_safe_calc_rejects_code(self) -> None:
        self.assertIn("Не смог", fun_act.calculate("__import__('os').system('id')"))

    @mock.patch("jarvis.actions.spotify.play_song", return_value="Включаю в Spotify: Test.")
    def test_spotify_play(self, mocked) -> None:
        result = parse_and_run("включи bohemian rhapsody в спотифай")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("bohemian rhapsody")

    @mock.patch("jarvis.actions.spotify.play_song", return_value="ok")
    def test_spotify_short(self, mocked) -> None:
        result = parse_and_run("спотифай lofti")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("lofti")

    @mock.patch("jarvis.actions.spotify.play_from_library", return_value="lib")
    def test_spotify_library(self, mocked) -> None:
        result = parse_and_run("включи shape of you из медиатеки")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("shape of you")

    @mock.patch("jarvis.actions.spotify.open_spotify", return_value="Открываю Spotify.")
    def test_spotify_open(self, mocked) -> None:
        result = parse_and_run("открой спотифай")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.spotify.open_liked_songs", return_value="liked")
    def test_spotify_liked(self, mocked) -> None:
        result = parse_and_run("открой медиатеку")
        self.assertTrue(result.ok)
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
