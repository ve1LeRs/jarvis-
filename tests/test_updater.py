from jarvis import updater


def test_release_build_parses_tag():
    assert updater._release_build({"tag_name": "build-42"}) == 42


def test_release_build_rejects_foreign_tags():
    assert updater._release_build({"tag_name": "v1.0"}) == -1
    assert updater._release_build({"tag_name": "build-x"}) == -1
    assert updater._release_build({}) == -1


def test_asset_url_finds_exe():
    release = {
        "assets": [
            {"name": "notes.txt", "browser_download_url": "a"},
            {"name": "JARVIS.exe", "browser_download_url": "b"},
        ]
    }
    assert updater._asset_url(release) == "b"
    assert updater._asset_url({"assets": []}) is None


def test_disabled_by_env(monkeypatch):
    monkeypatch.setenv("JARVIS_NO_UPDATE", "1")
    assert updater.check_and_update(lambda _m: None) is False
