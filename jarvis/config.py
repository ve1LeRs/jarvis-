"""JARVIS configuration."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

# Wake words (lowercase). Recognition is language-aware.
WAKE_WORDS = (
    "джарвис",
    "jarvis",
    "джервис",
    "джарвиз",
)

# Speech recognition language (Google Web Speech).
RECOGNITION_LANGUAGE = "ru-RU"

# Edge TTS voice (Russian, male, calm).
TTS_VOICE = os.getenv("JARVIS_VOICE", "ru-RU-DmitryNeural")
TTS_RATE = "+5%"
TTS_VOLUME = "+0%"

# Listening: only react to wake word, then wait for the full sentence to finish.
# pause_threshold = silence after speech before we treat the phrase as complete.
WAKE_PAUSE_THRESHOLD = 0.9
COMMAND_PAUSE_THRESHOLD = 1.6
# Max length of one capture (seconds). Combined = wake + command in one breath.
COMBINED_LISTEN_SECONDS = 14
COMMAND_LISTEN_SECONDS = 12

# Ambient energy calibration seconds on start.
ENERGY_CALIBRATION_SECONDS = 1.2

# UI
WINDOW_TITLE = "J.A.R.V.I.S."
ACCENT = "#00E5FF"
BG = "#050B12"
FG = "#E8F7FF"

# Default search engine template.
SEARCH_URL = "https://www.google.com/search?q={query}"

# Friendly spoken responses.
GREETINGS = (
    "Слушаю вас, сэр.",
    "Да, сэр?",
    "К вашим услугам.",
    "Готов, сэр.",
)

ACKNOWLEDGMENTS = (
    "Сделано.",
    "Выполняю.",
    "Уже открываю.",
    "Есть, сэр.",
)

NOT_UNDERSTOOD = (
    "Не совсем понял команду, сэр.",
    "Повторите, пожалуйста.",
    "Команда не распознана.",
)
