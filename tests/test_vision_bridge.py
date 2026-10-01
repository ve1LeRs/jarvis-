"""Tests for vision screen helpers and phone bridge."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from jarvis import bridge
from jarvis import confirm
from jarvis import context
from jarvis import llm
from jarvis import macros
from jarvis import memory
from jarvis.commands import parse_and_run
from jarvis.actions import screen


class VisionBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self._patchers = [
            mock.patch.object(memory, "DATA_DIR", root),
            mock.patch.object(memory, "SETTINGS_FILE", root / "settings.json"),
            mock.patch.object(memory, "NOTES_FILE", root / "notes.json"),
            mock.patch.object(memory, "HISTORY_FILE", root / "history.json"),
            mock.patch.object(memory, "TODOS_FILE", root / "todos.json"),
            mock.patch.object(macros, "MACROS_FILE", root / "macros.json"),
            mock.patch.object(bridge, "BRIDGE_FILE", root / "bridge.json"),
        ]
        for patcher in self._patchers:
            patcher.start()
        confirm.clear()
        context.set_mode("idle", quiet=False, apps=[])
        bridge.stop_all()

    def tearDown(self) -> None:
        bridge.stop_all()
        confirm.clear()
        for patcher in self._patchers:
            patcher.stop()
        self._tmp.cleanup()

    def test_describe_screen_uses_vision(self) -> None:
        with mock.patch.object(screen, "whats_on_screen", return_value="На экране: Chrome") as mocked:
            result = parse_and_run("опиши экран")
        self.assertTrue(result.ok)
        self.assertIn("Chrome", result.spoken)
        mocked.assert_called()

    def test_find_on_screen_routing(self) -> None:
        with mock.patch.object(screen, "find_on_screen", return_value="кнопка справа") as mocked:
            result = parse_and_run("найди на экране Сохранить")
        self.assertTrue(result.ok)
        mocked.assert_called_once_with("сохранить")

    def test_whats_on_screen_prefers_vision(self) -> None:
        img = Path(self._tmp.name) / "shot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        with mock.patch.object(screen, "_latest_screenshot", return_value=img), mock.patch(
            "jarvis.actions.system.take_screenshot", return_value="shot"
        ), mock.patch.object(llm, "describe_image", return_value="Открыт Discord с друзьями") as vision:
            text = screen.whats_on_screen()
        self.assertIn("Discord", text)
        vision.assert_called_once()

    def test_whats_on_screen_ocr_fallback(self) -> None:
        img = Path(self._tmp.name) / "shot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        with mock.patch.object(screen, "_latest_screenshot", return_value=img), mock.patch(
            "jarvis.actions.system.take_screenshot", return_value="shot"
        ), mock.patch.object(llm, "describe_image", return_value=None), mock.patch.object(
            screen, "_ocr_image", return_value="Hello World"
        ):
            text = screen.whats_on_screen()
        self.assertIn("Hello World", text)

    def test_telegram_token_preserves_colon(self) -> None:
        result = parse_and_run("сохрани телеграм токен 123456:ABC-DEF_secret")
        self.assertTrue(result.ok)
        self.assertIn("сохранён", result.spoken.lower())
        data = json.loads((Path(self._tmp.name) / "bridge.json").read_text(encoding="utf-8"))
        self.assertEqual(data.get("telegram_token"), "123456:ABC-DEF_secret")

    def test_bridge_http_command(self) -> None:
        parse_and_run("секрет моста testsecret")
        # Use a free port
        with mock.patch.object(bridge, "DEFAULT_PORT", 18765), mock.patch.dict(
            "os.environ", {"JARVIS_BRIDGE_PORT": "18765"}, clear=False
        ):
            # rewrite saved port
            data = bridge._load()
            data["port"] = 18765
            bridge._save(data)
            started = bridge.start_http()
            self.assertIn("18765", started)
            # wait until up
            for _ in range(20):
                if bridge.status()["http_running"]:
                    break
                threading.Event().wait(0.05)
            self.assertTrue(bridge.status()["http_running"])
            body = json.dumps({"text": "помощь", "secret": "testsecret"}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:18765/command",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode())
            self.assertTrue(payload.get("ok"))
            self.assertIn("Стек", payload.get("reply", ""))
            bridge.stop_http()

    def test_whatsapp_verify(self) -> None:
        data = bridge._load()
        data["port"] = 18766
        data["whatsapp_verify_token"] = "verifyme"
        bridge._save(data)
        bridge.start_http()
        for _ in range(20):
            if bridge.status()["http_running"]:
                break
            threading.Event().wait(0.05)
        url = (
            "http://127.0.0.1:18766/whatsapp?"
            "hub.mode=subscribe&hub.verify_token=verifyme&hub.challenge=12345"
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.read().decode(), "12345")
        bridge.stop_http()

    def test_bridge_status_command(self) -> None:
        result = parse_and_run("статус моста")
        self.assertTrue(result.ok)
        self.assertIn("Мост", result.spoken)


if __name__ == "__main__":
    unittest.main()
