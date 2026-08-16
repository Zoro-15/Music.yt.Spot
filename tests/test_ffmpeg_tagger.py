import unittest
from pathlib import Path
from downloader.ffmpeg_tagger import crop_square_artwork, apply_native_metadata
from downloader.cover_art import is_valid_cover_match, fetch_itunes_cover_art, fetch_deezer_cover_art, fetch_high_res_cover


class TestCoverArtAndTagger(unittest.TestCase):
    def test_is_valid_cover_match_genuine(self):
        # Exact match
        self.assertTrue(is_valid_cover_match("Blinding Lights", "The Weeknd", "Blinding Lights", "The Weeknd"))
        # Featuring/collaborator variation
        self.assertTrue(is_valid_cover_match("Starboy", "The Weeknd", "Starboy (feat. Daft Punk)", "The Weeknd"))
        # Single suffix
        self.assertTrue(is_valid_cover_match("Namastute", "Seedhe Maut", "Namastute - Single", "Seedhe Maut"))

    def test_is_valid_cover_match_rejects_different_song_same_artist(self):
        # Different song by same artist MUST be rejected! (This was the root cause of 10% wrong cover art)
        self.assertFalse(is_valid_cover_match("Toosie Slide", "Drake", "God's Plan", "Drake"))
        self.assertFalse(is_valid_cover_match("In My Feelings", "Drake", "Hotline Bling", "Drake"))

    def test_is_valid_cover_match_rejects_generic_short_titles_different_artist(self):
        # Generic short titles with different artists must be rejected
        self.assertFalse(is_valid_cover_match("One", "Metallica", "One More Light", "Linkin Park"))
        self.assertFalse(is_valid_cover_match("Stay", "The Kid LAROI", "Stay", "Rihanna"))
        self.assertFalse(is_valid_cover_match("Hello", "Adele", "Hello", "Lionel Richie"))

    def test_tagger_non_existent_file(self):
        fake_path = Path("non_existent_audio_file.mp3")
        success, msg = apply_native_metadata(fake_path, "Title", "Artist", "Album")
        self.assertFalse(success)
        self.assertIn("file does not exist", msg.lower())

    def test_crop_non_existent_artwork(self):
        fake_img = Path("non_existent_art.jpg")
        success, msg = crop_square_artwork(fake_img)
        self.assertFalse(success)
        self.assertIn("not found", msg.lower())

    def test_cover_art_fetch(self):
        img = fetch_high_res_cover("Blinding Lights", "The Weeknd")
        self.assertIsNotNone(img)
        self.assertGreater(len(img), 1000)


    def test_is_valid_cover_match_multilingual_and_collaborations(self):
        # Multi-artist collaboration
        self.assertTrue(is_valid_cover_match("Sunflower", "Post Malone, Swae Lee", "Sunflower (Spider-Man: Into the Spider-Verse)", "Post Malone & Swae Lee"))
        # Multilingual titles
        self.assertTrue(is_valid_cover_match("Kesariya", "Arijit Singh, Pritam", "Kesariya (From 'Brahmastra')", "Pritam, Arijit Singh"))
        self.assertTrue(is_valid_cover_match("295", "Sidhu Moose Wala", "295", "Sidhu Moose Wala"))
        # Mismatch multilingual
        self.assertFalse(is_valid_cover_match("Kesariya", "Arijit Singh", "Channa Mereya", "Arijit Singh"))

    def test_crop_image_bytes_to_square_isolated(self):
        from downloader.cover_art import crop_image_bytes_to_square
        # Empty/short bytes should return directly without error
        self.assertEqual(crop_image_bytes_to_square(b""), b"")
        self.assertEqual(crop_image_bytes_to_square(b"small_bytes"), b"small_bytes")


if __name__ == "__main__":
    unittest.main()
