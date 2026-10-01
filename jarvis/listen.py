"""Microphone listening and speech-to-text.

Activation rules:
- Ignore speech until a wake word («Джарвис») is heard.
- After wake word, keep listening until the speaker finishes the sentence
  (longer pause_threshold), instead of cutting mid-phrase.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Callable, Iterator

from jarvis import config


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s\-]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _wake_pattern(wake: str) -> str:
    return rf"(?:^|\s){re.escape(wake)}(?:\s|$)"


def contains_wake_word(text: str) -> bool:
    """True only when a wake word appears as its own word (not a substring)."""
    normalized = _normalize(text)
    return any(re.search(_wake_pattern(w), normalized) for w in config.WAKE_WORDS)


def strip_wake_word(text: str) -> str:
    """Keep only the part AFTER the wake word (command), drop preface."""
    normalized = _normalize(text)
    for wake in sorted(config.WAKE_WORDS, key=len, reverse=True):
        if normalized == wake:
            return ""
        if normalized.startswith(wake + " "):
            return normalized[len(wake) :].strip(" ,.-")
        # "эй джарвис открой …" → "открой …" (everything before wake is dropped)
        match = re.search(_wake_pattern(wake), normalized)
        if match:
            return normalized[match.end() :].strip(" ,.-")
    return normalized


def looks_like_command(text: str) -> bool:
    """Cheap heuristic: leftover after wake should have a real verb/intent word."""
    cleaned = _normalize(text)
    if not cleaned:
        return False
    # Single filler words after wake are not commands.
    if cleaned in {"а", "ну", "ээ", "эм", "пожалуйста", "сэр", "sir"}:
        return False
    # At least one meaningful token (2+ chars) beyond tiny fillers.
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    return bool(tokens)


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
        self._recognizer.pause_threshold = config.COMMAND_PAUSE_THRESHOLD
        self._recognizer.non_speaking_duration = min(0.6, config.WAKE_PAUSE_THRESHOLD)
        self._mic = sr.Microphone()
        self.on_status("Калибровка микрофона…")
        with self._mic as source:
            self._recognizer.adjust_for_ambient_noise(
                source, duration=config.ENERGY_CALIBRATION_SECONDS
            )
        self.on_status("Микрофон готов. Жду «Джарвис».")

    @contextmanager
    def _pause_settings(self, pause: float) -> Iterator[None]:
        assert self._recognizer is not None
        old_pause = self._recognizer.pause_threshold
        old_non = self._recognizer.non_speaking_duration
        self._recognizer.pause_threshold = pause
        self._recognizer.non_speaking_duration = min(0.6, pause * 0.45)
        try:
            yield
        finally:
            self._recognizer.pause_threshold = old_pause
            self._recognizer.non_speaking_duration = old_non

    def listen_once(
        self,
        *,
        phrase_time_limit: float | None = None,
        pause_threshold: float | None = None,
    ) -> str | None:
        import speech_recognition as sr

        if self._recognizer is None or self._mic is None:
            self.setup()

        assert self._recognizer is not None
        assert self._mic is not None

        pause = pause_threshold if pause_threshold is not None else config.COMMAND_PAUSE_THRESHOLD

        with self._pause_settings(pause):
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
        """Block until wake word, then return the full command sentence.

        - Speech without wake word is ignored.
        - If wake + command arrive in one utterance, use the remainder.
        - If only wake word is heard, keep listening until the command ends.
        """
        while True:
            # Patient capture so "Джарвис, … длинная команда" fits one utterance.
            uttered = self.listen_once(
                phrase_time_limit=config.COMBINED_LISTEN_SECONDS,
                pause_threshold=config.COMMAND_PAUSE_THRESHOLD,
            )
            if not uttered:
                continue
            if not contains_wake_word(uttered):
                # Activate only on wake word — ignore ambient speech.
                self.on_status("Жду «Джарвис»…")
                continue

            remainder = strip_wake_word(uttered)
            if looks_like_command(remainder):
                return remainder

            # Wake alone (or filler after it) — wait for the rest of the sentence.
            self.on_status("Джарвис активирован. Дослушиваю команду…")
            command = self.listen_once(
                phrase_time_limit=config.COMMAND_LISTEN_SECONDS,
                pause_threshold=config.COMMAND_PAUSE_THRESHOLD,
            )
            if not command:
                return None
            if contains_wake_word(command):
                stripped = strip_wake_word(command)
                return stripped if looks_like_command(stripped) else None
            normalized = _normalize(command)
            return normalized if looks_like_command(normalized) else None
