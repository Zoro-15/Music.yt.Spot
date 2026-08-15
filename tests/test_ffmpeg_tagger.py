import unittest
from pathlib import Path
from downloader.ffmpeg_tagger import crop_square_artwork, apply_native_metadata
from downloader.cover_art import fetch_itunes_cover_art, fetch_deezer_cover_art, fetch_high_res_cover


class TestFFmpegTagger(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()


