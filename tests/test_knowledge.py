"""Tests for spoken web answers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import memory
from jarvis import reminders
from jarvis.actions import knowledge
from jarvis.actions.knowledge import Answer
from jarvis.commands import parse_and_run


class KnowledgeUnitTests(unittest.TestCase):
    def test_is_question(self) -> None:
        self.assertTrue(knowledge.is_question("как переключить раскладку"))
        self.assertTrue(knowledge.is_question("что такое python"))
        self.assertFalse(knowledge.is_question("открой хром"))

    def test_builtin_keyboard_tip(self) -> None:
        tip = knowledge._builtin_tip("как переключить раскладку на клавиатуре")
        self.assertIsNotNone(tip)
        assert tip is not None
        self.assertIn("Win", tip)

    @mock.patch.object(knowledge, "_ddg_instant", return_value=None)
    @mock.patch.object(knowledge, "_ddg_html_snippets", return_value=[])
    @mock.patch.object(knowledge, "_wikipedia_summary", return_value=None)
    @mock.patch.object(knowledge.sys_act, "search_web", return_value="opened")
    def test_lookup_uses_builtin_tip(self, _web, _wiki, _html, _inst) -> None:
        answer = knowledge.lookup("как переключить раскладку клавиатуры", open_browser=True)
        self.assertIn("Win", answer.spoken)
        self.assertTrue(answer.opened_browser)


class KnowledgeCommandTests(unittest.TestCase):
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

    @mock.patch(
        "jarvis.actions.knowledge.lookup",
        return_value=Answer(
            spoken="В Windows раскладку переключают Win + пробел.",
            source="подсказка JARVIS",
            opened_browser=True,
        ),
    )
    def test_how_question(self, mocked) -> None:
        result = parse_and_run("как переключить раскладку на клавиатуре")
        self.assertTrue(result.ok)
        self.assertIn("Win", result.spoken)
        mocked.assert_called_once()
        self.assertEqual(
            mocked.call_args.args[0],
            "как переключить раскладку на клавиатуре",
        )

    @mock.patch(
        "jarvis.actions.knowledge.lookup",
        return_value=Answer(spoken="Python — язык программирования.", source="Википедия"),
    )
    def test_what_is(self, mocked) -> None:
        result = parse_and_run("что такое python")
        self.assertTrue(result.ok)
        self.assertIn("Python", result.spoken)
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
