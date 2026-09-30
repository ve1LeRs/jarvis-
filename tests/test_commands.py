"""Unit tests for command parsing (no microphone needed)."""

from __future__ import annotations

import unittest
from unittest import mock

from jarvis.commands import parse_and_run
from jarvis.listen import contains_wake_word, strip_wake_word


class WakeWordTests(unittest.TestCase):
    def test_wake_detected(self) -> None:
        self.assertTrue(contains_wake_word("Джарвис, открой проводник"))
        self.assertTrue(contains_wake_word("jarvis open chrome"))

    def test_strip(self) -> None:
        self.assertEqual(strip_wake_word("джарвис открой проводник"), "открой проводник")


class CommandTests(unittest.TestCase):
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

    def test_help(self) -> None:
        result = parse_and_run("помощь")
        self.assertTrue(result.ok)

    @mock.patch("jarvis.autostart.enable_autostart", return_value="enabled")
    def test_autostart_on(self, mocked) -> None:
        result = parse_and_run("включи автозапуск")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    def test_unknown(self) -> None:
        result = parse_and_run("блаблабла xyz")
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
