"""J.A.R.V.I.S. — голосовой ассистент.

Запуск:
  python -m jarvis                 # голос + HUD
  python -m jarvis --overlay       # компактный оверлей
  python -m jarvis --background    # фон / автозапуск (трей, без консоли)
  python -m jarvis --text          # текстовый режим
  python -m jarvis --no-ui         # голос без окна
"""

from __future__ import annotations

import argparse
import random
import sys
import threading

from jarvis import config
from jarvis import context
from jarvis import hotkeys
from jarvis import memory
from jarvis import plugins
from jarvis import proactive
from jarvis import reminders
from jarvis.commands import parse_and_run
from jarvis import speak as speak_mod


def speak(text: str, *, block: bool = True) -> None:
    speak_mod.speak(context.adapt_speech(text), block=block)


reminders.set_speaker(lambda text: speak(text, block=False))
proactive.set_speaker(lambda text: speak(text, block=False))


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


def run_text_loop(on_status, stop_event: threading.Event | None = None) -> None:
    on_status("Текстовый режим. Пишите команды (или 'выход').")
    speak(random.choice(config.GREETINGS), block=False)
    while not (stop_event and stop_event.is_set()):
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
        from jarvis.listen import contains_wake_word, strip_wake_word

        command = strip_wake_word(line) if contains_wake_word(line) else line
        result = parse_and_run(command)
        on_status(result.spoken)
        speak(result.spoken)
        if result.detail == "__EXIT__":
            break


def _handle_command(command: str, on_status) -> bool:
    """Run one command; return True if the loop should exit."""
    on_status(f"Команда: {command}")
    result = parse_and_run(command)
    on_status(result.spoken)
    speak(result.spoken)
    return result.detail == "__EXIT__"


def run_voice_loop(on_status, stop_event: threading.Event | None = None) -> None:
    from jarvis.listen import Listener

    listener = Listener(on_status=on_status)
    try:
        listener.setup()
    except Exception as exc:  # noqa: BLE001
        on_status(f"Микрофон недоступен: {exc}")
        on_status("Переключаюсь в текстовый режим.")
        run_text_loop(on_status, stop_event=stop_event)
        return

    speak(random.choice(config.GREETINGS))
    on_status("Скажите «Джарвис» и команду. Или Ctrl+Alt+J (push-to-talk).")

    ptt_busy = threading.Lock()

    def on_ptt() -> None:
        if not ptt_busy.acquire(blocking=False):
            return
        try:
            on_status("Push-to-talk: говорите команду…")
            uttered = listener.listen_once(phrase_time_limit=config.COMMAND_LISTEN_SECONDS)
            if not uttered:
                speak(random.choice(config.NOT_UNDERSTOOD), block=False)
                return
            from jarvis.listen import contains_wake_word, strip_wake_word, _normalize

            command = strip_wake_word(uttered) if contains_wake_word(uttered) else _normalize(uttered)
            if command and _handle_command(command, on_status):
                if stop_event:
                    stop_event.set()
        finally:
            ptt_busy.release()

    ptt = hotkeys.PushToTalk(on_ptt)
    if ptt.start():
        on_status(hotkeys.describe_default())
    elif ptt.error:
        on_status(ptt.error)

    try:
        while not (stop_event and stop_event.is_set()):
            try:
                command = listener.listen_for_wake_then_command()
            except KeyboardInterrupt:
                break
            if stop_event and stop_event.is_set():
                break
            if not command:
                speak(random.choice(config.NOT_UNDERSTOOD), block=False)
                continue
            if _handle_command(command, on_status):
                if stop_event:
                    stop_event.set()
                break
    finally:
        ptt.stop()


def run_background() -> int:
    """Autostart / background: voice listener + system tray, optional HUD."""
    stop_event = threading.Event()
    hud_holder: dict = {"hud": None}

    def on_status(msg: str) -> None:
        print(msg)
        hud = hud_holder.get("hud")
        if hud is not None:
            try:
                hud.set_status(msg)
            except Exception:
                pass

    worker = threading.Thread(
        target=run_voice_loop,
        args=(on_status, stop_event),
        daemon=True,
    )
    worker.start()

    def on_quit() -> None:
        stop_event.set()
        hud = hud_holder.get("hud")
        if hud is not None:
            try:
                hud.close()
            except Exception:
                pass
        # Force exit — mic listen may block
        threading.Timer(0.5, lambda: os_exit()).start()

    def os_exit() -> None:
        import os

        os._exit(0)

    def on_show() -> None:
        # Open HUD window in a dedicated thread with its own Tk — Tk must stay on one thread.
        def _ui() -> None:
            from jarvis.ui.hud import JarvisHUD

            hud = JarvisHUD()
            hud_holder["hud"] = hud
            hud.set_status("J.A.R.V.I.S. работает в фоне. Скажите «Джарвис».")
            hud.run()
            hud_holder["hud"] = None

        if hud_holder.get("hud") is None:
            threading.Thread(target=_ui, daemon=True).start()

    def on_mute_toggle() -> None:
        memory.set_muted(not memory.is_muted())
        state = "выключен" if memory.is_muted() else "включён"
        on_status(f"Голос {state}.")

    try:
        from jarvis.ui.tray import run_tray

        run_tray(on_show=on_show, on_quit=on_quit, on_mute_toggle=on_mute_toggle)
    except Exception as exc:  # noqa: BLE001
        on_status(f"Трей недоступен ({exc}). Работаю без иконки — закройте процесс вручную.")
        try:
            stop_event.wait()
        except KeyboardInterrupt:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. voice assistant")
    parser.add_argument("--text", action="store_true", help="Text input instead of microphone")
    parser.add_argument("--no-ui", action="store_true", help="Disable HUD window")
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Compact always-on-top overlay instead of full HUD",
    )
    parser.add_argument("--no-speak", action="store_true", help="Disable TTS (print only)")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Background / autostart mode: tray icon, no console UI",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Enable Windows autostart and exit",
    )
    parser.add_argument(
        "--remove-autostart",
        action="store_true",
        help="Disable Windows autostart and exit",
    )
    parser.add_argument(
        "--desktop-shortcut",
        action="store_true",
        help="Create desktop shortcut and exit",
    )
    parser.add_argument(
        "--install-app",
        action="store_true",
        help="Install as Windows app: desktop, Start Menu, autostart",
    )
    parser.add_argument(
        "--uninstall-app",
        action="store_true",
        help="Remove desktop/Start Menu/autostart shortcuts",
    )
    args = parser.parse_args(argv)

    if (
        args.install_autostart
        or args.remove_autostart
        or args.desktop_shortcut
        or args.install_app
        or args.uninstall_app
    ):
        from jarvis import autostart

        if args.install_app:
            print(autostart.install_as_app(with_autostart=True))
            return 0
        if args.uninstall_app:
            print(autostart.uninstall_app())
            return 0
        if args.install_autostart:
            print(autostart.enable_autostart())
            print(autostart.create_desktop_shortcut())
            print(autostart.create_start_menu_shortcuts())
        if args.remove_autostart:
            print(autostart.disable_autostart())
        if args.desktop_shortcut and not args.install_autostart:
            print(autostart.create_desktop_shortcut())
        return 0

    if args.no_speak:
        speak_mod.speak = lambda text, block=True: print(f"JARVIS: {text}")  # type: ignore[assignment]

    # Boot helpers: cached app paths, plugins, proactive nudges.
    try:
        from jarvis import paths as paths_mod

        paths_mod.ensure_detected()
    except Exception:
        pass
    try:
        plugins.reload()
    except Exception:
        pass
    try:
        proactive.start()
    except Exception:
        pass

    if args.background:
        return run_background()

    _banner()

    if args.no_ui:
        on_status = print
        if args.text:
            run_text_loop(on_status)
        else:
            run_voice_loop(on_status)
        return 0

    if args.overlay:
        from jarvis.ui.overlay import JarvisOverlay

        ui = JarvisOverlay()
    else:
        from jarvis.ui.hud import JarvisHUD

        ui = JarvisHUD()

    def on_status(msg: str) -> None:
        print(msg)
        ui.set_status(msg)

    worker = threading.Thread(
        target=run_text_loop if args.text else run_voice_loop,
        args=(on_status,),
        daemon=True,
    )
    worker.start()
    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
