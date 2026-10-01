"""Tests for self-update helpers."""

from __future__ import annotations

import os
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

    def test_frozen_up_to_date_message(self) -> None:
        with mock.patch.object(updater.sys, "frozen", True, create=True), mock.patch.object(
            updater, "_fetch_latest_release", return_value={"tag_name": f"build-{updater.BUILD}"}
        ):
            msg = updater.update_from_git()
        self.assertIn("последняя версия", msg)


if __name__ == "__main__":
    unittest.main()
