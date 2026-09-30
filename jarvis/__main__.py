"""J.A.R.V.I.S. — голосовой ассистент.

Запуск:
  python -m jarvis                 # голос + HUD
  python -m jarvis --text          # текстовый режим (без микрофона)
  python -m jarvis --no-ui         # голос без окна
  python -m jarvis --text --no-ui  # только консоль
"""

from __future__ import annotations

import argparse
import random
import sys
import threading

from jarvis import config
from jarvis.commands import parse_and_run
from jarvis import speak as speak_mod


def speak(text: str, *, block: bool = True) -> None:
    speak_mod.speak(text, block=block)


def _banner() -> None:
    print(
        r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
        Just A Rather Very Intelligent System
"""
    )


def run_text_loop(on_status) -> None:
    on_status("Текстовый режим. Пишите команды (или 'выход').")
    speak(random.choice(config.GREETINGS), block=False)
    while True:
        try:
            line = input("Вы > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in {"выход", "exit", "quit", "пока"}:
            speak("До связи, сэр.")
            break
        # Allow typing with or without wake word.
        from jarvis.listen import contains_wake_word, strip_wake_word

        command = strip_wake_word(line) if contains_wake_word(line) else line
        result = parse_and_run(command)
        on_status(result.spoken)
        speak(result.spoken)
        if result.detail == "__EXIT__":
            break


def run_voice_loop(on_status) -> None:
    from jarvis.listen import Listener

    listener = Listener(on_status=on_status)
    try:
        listener.setup()
    except Exception as exc:  # noqa: BLE001
        on_status(f"Микрофон недоступен: {exc}")
        on_status("Переключаюсь в текстовый режим.")
        run_text_loop(on_status)
        return

    speak(random.choice(config.GREETINGS))
    on_status("Скажите «Джарвис» и команду.")

    while True:
        try:
            command = listener.listen_for_wake_then_command()
        except KeyboardInterrupt:
            break
        if not command:
            speak(random.choice(config.NOT_UNDERSTOOD), block=False)
            continue
        on_status(f"Команда: {command}")
        result = parse_and_run(command)
        on_status(result.spoken)
        speak(result.spoken)
        if result.detail == "__EXIT__":
            break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. voice assistant")
    parser.add_argument("--text", action="store_true", help="Text input instead of microphone")
    parser.add_argument("--no-ui", action="store_true", help="Disable HUD window")
    parser.add_argument("--no-speak", action="store_true", help="Disable TTS (print only)")
    args = parser.parse_args(argv)

    if args.no_speak:
        speak_mod.speak = lambda text, block=True: print(f"JARVIS: {text}")  # type: ignore[assignment]

    _banner()

    if args.no_ui:
        on_status = print
        if args.text:
            run_text_loop(on_status)
        else:
            run_voice_loop(on_status)
        return 0

    from jarvis.ui.hud import JarvisHUD

    hud = JarvisHUD()

    def on_status(msg: str) -> None:
        print(msg)
        hud.set_status(msg)

    worker = threading.Thread(
        target=run_text_loop if args.text else run_voice_loop,
        args=(on_status,),
        daemon=True,
    )
    worker.start()
    try:
        hud.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
