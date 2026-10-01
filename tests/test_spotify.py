"""Unit tests for Spotify helpers (no real app/network)."""

from __future__ import annotations

import unittest
from unittest import mock

from jarvis.actions import spotify


class SpotifyActionTests(unittest.TestCase):
    @mock.patch.object(spotify, "_press_enter")
    @mock.patch.object(spotify, "_open_uri", return_value=True)
    @mock.patch.object(spotify, "open_spotify", return_value="Открываю Spotify.")
    @mock.patch.object(spotify, "_api_configured", return_value=False)
    @mock.patch.object(spotify.time, "sleep")
    def test_play_song_uri_fallback(self, _sleep, _api, _open, open_uri, _enter) -> None:
        msg = spotify.play_song("bohemian rhapsody")
        self.assertIn("bohemian rhapsody", msg.lower())
        open_uri.assert_any_call("spotify:search:bohemian%20rhapsody")

    @mock.patch.object(spotify, "_play_uris", return_value=True)
    @mock.patch.object(spotify, "search_track")
    @mock.patch.object(spotify, "open_spotify", return_value="ok")
    @mock.patch.object(spotify, "_api_configured", return_value=True)
    @mock.patch.object(spotify.time, "sleep")
    def test_play_song_api(self, _sleep, _api, _open, search, play) -> None:
        search.return_value = {
            "name": "Song",
            "uri": "spotify:track:abc",
            "artists": [{"name": "Artist"}],
            "id": "abc",
        }
        msg = spotify.play_song("song")
        self.assertIn("Song", msg)
        play.assert_called_once_with(["spotify:track:abc"])


if __name__ == "__main__":
    unittest.main()
