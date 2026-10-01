"""Long-term user facts and sentence-wise speech chunking."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import facts
from jarvis import llm
from jarvis import memory
from jarvis.commands import parse_and_run
from jarvis.speak import split_for_speech


class FactsTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        for patcher in self._patchers:
            patcher.stop()
        self._tmp.cleanup()

    def test_remember_keeps_casing_and_skips_notes(self) -> None:
        result = parse_and_run("Запомни, что я болею за Спартак")
        self.assertTrue(result.ok)
        self.assertIn("Я болею за Спартак", result.spoken)
        self.assertEqual(facts.all_facts(), ["Я болею за Спартак"])
        self.assertIn("Заметок пока нет", memory.list_notes())

    def test_plain_zapomni_is_still_a_note(self) -> None:
        parse_and_run("запомни купить молоко")
        self.assertEqual(facts.all_facts(), [])
        self.assertIn("купить молоко", memory.list_notes())

    def test_duplicate_not_stored_twice(self) -> None:
        facts.add("меня зовут Алекс")
        self.assertIn("уже помню", facts.add("Меня зовут Алекс."))
        self.assertEqual(len(facts.all_facts()), 1)

    def test_list(self) -> None:
        self.assertIn("ничего", parse_and_run("что ты обо мне знаешь").spoken)
        facts.add("моя машина — Тойота")
        result = parse_and_run("что ты знаешь обо мне")
        self.assertIn("Моя машина — Тойота", result.spoken)

    def test_personal_question_answered_from_facts(self) -> None:
        facts.add("меня зовут Алекс")
        facts.add("мой день рождения 5 мая")
        self.assertIn("Алекс", parse_and_run("как меня зовут").spoken)
        self.assertIn("5 мая", parse_and_run("когда мой день рождения").spoken)

    def test_unrelated_question_not_hijacked(self) -> None:
        facts.add("мой день рождения 5 мая")
        self.assertIsNone(facts.answer("какая моя любимая игра"))
        self.assertIsNone(facts.answer("какой день недели"))

    def test_forget(self) -> None:
        facts.add("моя машина — Тойота")
        facts.add("я болею за Спартак")
        self.assertIn("Забыл", parse_and_run("забудь про машину").spoken)
        self.assertEqual(facts.all_facts(), ["Я болею за Спартак"])

    def test_clear_requires_confirmation(self) -> None:
        facts.add("я болею за Спартак")
        parse_and_run("забудь всё обо мне")
        self.assertEqual(len(facts.all_facts()), 1)
        parse_and_run("подтверди")
        self.assertEqual(facts.all_facts(), [])

    def test_facts_injected_into_llm_prompt(self) -> None:
        facts.add("меня зовут Алекс")
        with mock.patch.object(llm, "available", return_value=True), mock.patch.object(
            llm, "_chat", return_value="Конечно, Алекс."
        ) as chat:
            llm.answer("посоветуй фильм")
        self.assertIn("Меня зовут Алекс", chat.call_args.kwargs["system"])


class SpeechChunkTests(unittest.TestCase):
    def test_short_text_single_chunk(self) -> None:
        self.assertEqual(split_for_speech("Сделано."), ["Сделано."])

    def test_first_chunk_is_short_rest_merged(self) -> None:
        text = (
            "Это первое, достаточно длинное предложение ответа. Второе предложение. "
            "Третье предложение. Четвёртое предложение."
        )
        chunks = split_for_speech(text)
        self.assertEqual(chunks[0], "Это первое, достаточно длинное предложение ответа.")
        self.assertEqual(chunks[1], "Второе предложение. Третье предложение. Четвёртое предложение.")

    def test_tiny_first_sentence_merged_with_next(self) -> None:
        chunks = split_for_speech("Да, сэр. Открываю браузер и ищу информацию.")
        self.assertEqual(chunks, ["Да, сэр. Открываю браузер и ищу информацию."])

    def test_long_sentence_split(self) -> None:
        text = ", ".join(["очень длинная часть фразы"] * 30) + "."
        chunks = split_for_speech(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 260 for c in chunks))
        self.assertEqual(" ".join(chunks).replace("  ", " "), text)


if __name__ == "__main__":
    unittest.main()
