"""Microphone listening and speech-to-text."""

from __future__ import annotations

import re
from typing import Callable

from jarvis import config


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s\-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_wake_word(text: str) -> bool:
    normalized = _normalize(text)
    return any(w in normalized for w in config.WAKE_WORDS)


def strip_wake_word(text: str) -> str:
    normalized = _normalize(text)
    for wake in sorted(config.WAKE_WORDS, key=len, reverse=True):
        if normalized.startswith(wake):
            return normalized[len(wake) :].strip(" ,.-")
        # "эй джарвис ..." / "ок джарвис ..."
        pattern = rf"(?:^|\s){re.escape(wake)}(?:\s|$)"
        if re.search(pattern, normalized):
            return re.sub(pattern, " ", normalized, count=1).strip(" ,.-")
    return normalized


class Listener:
    """Continuous microphone listener using SpeechRecognition."""

    def __init__(self, on_status: Callable[[str], None] | None = None) -> None:
        self.on_status = on_status or (lambda _s: None)
        self._recognizer = None
        self._mic = None

    def setup(self) -> None:
        import speech_recognition as sr

        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = 0.7
        self._mic = sr.Microphone()
        self.on_status("Калибровка микрофона…")
        with self._mic as source:
            self._recognizer.adjust_for_ambient_noise(
                source, duration=config.ENERGY_CALIBRATION_SECONDS
            )
        self.on_status("Микрофон готов.")

    def listen_once(self, *, phrase_time_limit: float | None = None) -> str | None:
        import speech_recognition as sr

        if self._recognizer is None or self._mic is None:
            self.setup()

        assert self._recognizer is not None
        assert self._mic is not None

        with self._mic as source:
            self.on_status("Слушаю…")
            try:
                audio = self._recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=phrase_time_limit,
                )
            except sr.WaitTimeoutError:
                return None

        self.on_status("Распознаю речь…")
        try:
            text = self._recognizer.recognize_google(
                audio, language=config.RECOGNITION_LANGUAGE
            )
            self.on_status(f"Вы сказали: {text}")
            return text
        except sr.UnknownValueError:
            self.on_status("Не расслышал.")
            return None
        except sr.RequestError as exc:
            self.on_status(f"Ошибка распознавания: {exc}")
            return None

    def listen_for_wake_then_command(self) -> str | None:
        """Block until wake word, then capture the rest of the command."""
        while True:
            uttered = self.listen_once(phrase_time_limit=config.WAKE_PHRASE_TIME_LIMIT)
            if not uttered:
                continue
            if not contains_wake_word(uttered):
                continue

            remainder = strip_wake_word(uttered)
            if remainder:
                return remainder

            # Wake alone — listen for the actual command.
            self.on_status("Wake word. Жду команду…")
            command = self.listen_once(phrase_time_limit=config.COMMAND_LISTEN_SECONDS)
            if command:
                return strip_wake_word(command) if contains_wake_word(command) else _normalize(command)
            return None
