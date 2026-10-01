"""Tests for self-update helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import updater
from jarvis.commands import parse_and_run


class UpdaterTests(unittest.TestCase):
    def test_status_routing(self) -> None:
        with mock.patch.object(updater, "status_text", return_value="Git: ветка main."):
            result = parse_and_run("версия")
        self.assertTrue(result.ok)
        self.assertIn("ветка", result.spoken)

    def test_update_routing(self) -> None:
        with mock.patch.object(
            updater, "update_from_git", return_value="Код обновлён. Сейчас: abc1234"
        ) as mocked:
            result = parse_and_run("обнови джарвис")
        self.assertTrue(result.ok)
        self.assertIn("обновлён", result.spoken)
        mocked.assert_called_once()

    def test_not_git_message(self) -> None:
        with mock.patch.object(updater, "project_root", return_value=Path("/tmp/not-a-repo")), mock.patch.object(
            updater, "is_git_checkout", return_value=False
        ), mock.patch.object(updater.sys, "frozen", False, create=True):
            msg = updater.update_from_git(install_deps=False)
        self.assertIn("git clone", msg.lower())

    def test_is_git_checkout_true_here(self) -> None:
        self.assertTrue(updater.is_git_checkout(Path(__file__).resolve().parents[1]))


class ReleaseUpdaterTests(unittest.TestCase):
    def test_release_build_parses_tag(self) -> None:
        self.assertEqual(updater._release_build({"tag_name": "build-42"}), 42)

    def test_release_build_rejects_foreign_tags(self) -> None:
        self.assertEqual(updater._release_build({"tag_name": "v1.0"}), -1)
        self.assertEqual(updater._release_build({"tag_name": "build-x"}), -1)
        self.assertEqual(updater._release_build({}), -1)

    def test_asset_url_finds_exe(self) -> None:
        release = {
            "assets": [
                {"name": "notes.txt", "browser_download_url": "a"},
                {"name": "JARVIS.exe", "browser_download_url": "b"},
            ]
        }
        self.assertEqual(updater._asset_url(release), "b")
        self.assertIsNone(updater._asset_url({"assets": []}))

    def test_disabled_by_env(self) -> None:
        with mock.patch.dict(os.environ, {"JARVIS_NO_UPDATE": "1"}):
            self.assertFalse(updater.check_and_update(lambda _m: None))

    def test_swap_renames_running_exe_and_starts_new_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            current = folder / "JARVIS.exe"
            new = folder / "JARVIS.new.exe"
            current.write_bytes(b"old build")
            new.write_bytes(b"new build")
            with mock.patch.object(updater.sys, "executable", str(current)), mock.patch.object(
                updater.sys, "argv", ["JARVIS.exe", "--background"]
            ), mock.patch.object(updater.subprocess, "Popen") as popen, mock.patch.object(
                updater.os, "_exit", side_effect=SystemExit
            ):
                with self.assertRaises(SystemExit):
                    updater._restart_with_new_exe(new)
            self.assertEqual(current.read_bytes(), b"new build")
            self.assertEqual((folder / "JARVIS.old.exe").read_bytes(), b"old build")
            self.assertFalse(new.exists())
            self.assertEqual(popen.call_args.args[0], [str(current.resolve()), "--background"])

    def test_swap_rolls_back_when_new_exe_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            current = Path(tmp) / "JARVIS.exe"
            current.write_bytes(b"old build")
            with mock.patch.object(updater.sys, "executable", str(current)), mock.patch.object(
                updater.subprocess, "Popen"
            ) as popen:
                with self.assertRaises(OSError):
                    updater._restart_with_new_exe(Path(tmp) / "missing.exe")
            self.assertEqual(current.read_bytes(), b"old build")
            popen.assert_not_called()

    def test_child_env_drops_pyinstaller_state(self) -> None:
        meipass = r"C:\Temp\_MEI12345"
        env = {
            "_PYI_APPLICATION_HOME_DIR": meipass,
            "_MEIPASS2": meipass,
            "TCL_LIBRARY": meipass + r"\tcl",
            "PATH": meipass + r";C:\Windows",
            "USERPROFILE": r"C:\Users\me",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            updater.sys, "_MEIPASS", meipass, create=True
        ):
            child = updater._clean_child_env()
        self.assertEqual(child["PATH"], r"C:\Windows")
        self.assertEqual(child["USERPROFILE"], r"C:\Users\me")
        self.assertEqual(child["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        for key in ("_PYI_APPLICATION_HOME_DIR", "_MEIPASS2", "TCL_LIBRARY"):
            self.assertNotIn(key, child)

    def test_version_label(self) -> None:
        with mock.patch.object(updater, "BUILD", 7):
            self.assertEqual(updater.version_label(), "сборка 7")
        with mock.patch.object(updater, "BUILD", 0):
            self.assertTrue(updater.version_label().startswith("dev"))

    def test_update_notice_shown_once_after_upgrade(self) -> None:
        settings: dict = {}
        with mock.patch("jarvis.memory.get_settings", side_effect=lambda: dict(settings)), mock.patch(
            "jarvis.memory.update_settings", side_effect=lambda **kw: settings.update(kw)
        ):
            with mock.patch.object(updater, "BUILD", 5):
                self.assertIsNone(updater.take_update_notice())  # first run: nothing to compare
            with mock.patch.object(updater, "BUILD", 6):
                self.assertEqual(updater.take_update_notice(), "JARVIS обновлён: сборка 5 → 6.")
                self.assertIsNone(updater.take_update_notice())

    def test_frozen_up_to_date_message(self) -> None:
        with mock.patch.object(updater.sys, "frozen", True, create=True), mock.patch.object(
            updater, "_fetch_latest_release", return_value={"tag_name": f"build-{updater.BUILD}"}
        ):
            msg = updater.update_from_git()
        self.assertIn("последняя версия", msg)


if __name__ == "__main__":
    unittest.main()
