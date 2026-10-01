"""Unit tests for command parsing (no microphone needed)."""

from __future__ import annotations

import unittest
from unittest import mock

from jarvis.commands import parse_and_run
from jarvis.listen import contains_wake_word, looks_like_command, strip_wake_word


class WakeWordTests(unittest.TestCase):
    def test_wake_detected(self) -> None:
        self.assertTrue(contains_wake_word("Джарвис, открой проводник"))
        self.assertTrue(contains_wake_word("jarvis open chrome"))
        self.assertTrue(contains_wake_word("эй джарвис который час"))

    def test_wake_not_substring(self) -> None:
        self.assertFalse(contains_wake_word("открой проводник"))
        self.assertFalse(contains_wake_word("просто разговор без активации"))

    def test_strip(self) -> None:
        self.assertEqual(strip_wake_word("джарвис открой проводник"), "открой проводник")
        self.assertEqual(strip_wake_word("джарвис"), "")
        self.assertEqual(
            strip_wake_word("эй джарвис найди информацию о брусе"),
            "найди информацию о брусе",
        )

    def test_looks_like_command(self) -> None:
        self.assertTrue(looks_like_command("открой проводник"))
        self.assertTrue(looks_like_command("найди информацию о сосновом брусе"))
        self.assertFalse(looks_like_command(""))
        self.assertFalse(looks_like_command("ну"))
        self.assertFalse(looks_like_command("пожалуйста"))


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

    @mock.patch("jarvis.actions.system.open_explorer", return_value="explorer")
    def test_explorer_with_please(self, mocked) -> None:
        result = parse_and_run("открой проводник пожалуйста")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.system.open_explorer", return_value="explorer")
    def test_explorer_with_wake_leftover(self, mocked) -> None:
        result = parse_and_run("джарвис открой проводник")
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

    @mock.patch("jarvis.actions.system.open_steam", return_value="steam")
    def test_steam(self, mocked) -> None:
        result = parse_and_run("открой стим")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

    @mock.patch("jarvis.actions.system.open_steam", return_value="steam")
    def test_steam_english(self, mocked) -> None:
        result = parse_and_run("открой steam")
        self.assertTrue(result.ok)
        mocked.assert_called_once()

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


class ListenFlowTests(unittest.TestCase):
    def test_full_sentence_after_wake_in_one_utterance(self) -> None:
        from jarvis.listen import Listener

        listener = Listener(on_status=lambda _s: None)
        calls = {"n": 0}

        def fake_listen_once(**_kwargs):
            calls["n"] += 1
            return "Джарвис, открой проводник"

        listener.listen_once = fake_listen_once  # type: ignore[method-assign]
        cmd = listener.listen_for_wake_then_command()
        self.assertEqual(cmd, "открой проводник")
        self.assertEqual(calls["n"], 1)

    def test_ignores_speech_without_wake(self) -> None:
        from jarvis.listen import Listener

        listener = Listener(on_status=lambda _s: None)
        sequence = iter(
            [
                "просто фоновый разговор",
                "Джарвис который час",
            ]
        )

        def fake_listen_once(**_kwargs):
            return next(sequence)

        listener.listen_once = fake_listen_once  # type: ignore[method-assign]
        cmd = listener.listen_for_wake_then_command()
        self.assertEqual(cmd, "который час")

    def test_wake_alone_then_command(self) -> None:
        from jarvis.listen import Listener

        listener = Listener(on_status=lambda _s: None)
        sequence = iter(["Джарвис", "открой ютуб"])

        def fake_listen_once(**_kwargs):
            return next(sequence)

        listener.listen_once = fake_listen_once  # type: ignore[method-assign]
        cmd = listener.listen_for_wake_then_command()
        self.assertEqual(cmd, "открой ютуб")


class SteamPathTests(unittest.TestCase):
    @mock.patch("jarvis.actions.system.SYSTEM", "Windows")
    def test_prefers_program_files_x86(self) -> None:
        from jarvis.actions import system as act

        wanted = r"C:\Program Files (x86)\Steam\steam.exe"
        with mock.patch("os.path.isfile", side_effect=lambda p: p == wanted):
            self.assertEqual(act._find_steam(), wanted)


class VoicePickerTests(unittest.TestCase):
    def test_prefers_male_russian(self) -> None:
        from jarvis.speak import _pick_male_russian_voice

        class Voice:
            def __init__(self, name: str, vid: str, languages=None) -> None:
                self.name = name
                self.id = vid
                self.languages = languages or []

        class Engine:
            def __init__(self, voices) -> None:
                self._voices = voices

            def getProperty(self, _key: str):
                return self._voices

        engine = Engine(
            [
                Voice("Microsoft Irina Desktop - Russian", "irina", ["ru-RU"]),
                Voice("Microsoft Pavel - Russian", "pavel", ["ru-RU"]),
                Voice("Microsoft Zira Desktop - English (United States)", "zira"),
            ]
        )
        self.assertEqual(_pick_male_russian_voice(engine), "pavel")


if __name__ == "__main__":
    unittest.main()
