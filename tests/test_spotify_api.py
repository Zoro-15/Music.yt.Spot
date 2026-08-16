import unittest
from downloader.spotify_api import parse_spotify_url


class TestSpotifyAPI(unittest.TestCase):
    def test_parse_spotify_url_playlist(self):
        item_type, item_id = parse_spotify_url("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=123")
        self.assertEqual(item_type, "playlist")
        self.assertEqual(item_id, "37i9dQZF1DXcBWIGoYBM5M")

    def test_parse_spotify_url_album(self):
        item_type, item_id = parse_spotify_url("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy")
        self.assertEqual(item_type, "album")
        self.assertEqual(item_id, "4aawyAB9vmqN3uQ7FjRGTy")

    def test_parse_spotify_url_track(self):
        item_type, item_id = parse_spotify_url("https://open.spotify.com/track/0VjLj2DipiyLwoxbeRppwU")
        self.assertEqual(item_type, "track")
        self.assertEqual(item_id, "0VjLj2DipiyLwoxbeRppwU")

    def test_parse_spotify_uri(self):
        item_type, item_id = parse_spotify_url("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
        self.assertEqual(item_type, "playlist")
        self.assertEqual(item_id, "37i9dQZF1DXcBWIGoYBM5M")

    def test_parse_invalid_url(self):
        item_type, item_id = parse_spotify_url("https://youtube.com/watch?v=12345")
        self.assertIsNone(item_type)
        self.assertIsNone(item_id)


if __name__ == "__main__":
    unittest.main()
