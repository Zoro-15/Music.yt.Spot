import unittest
from downloader.utils import normalize, words, sanitize_filename, clean_title_and_artist


class TestUtils(unittest.TestCase):
    def test_normalize_basic(self):
        self.assertEqual(normalize("  Hello  World!  "), "hello world")
        self.assertEqual(normalize("Song - Name (Official Audio)"), "song name official audio")

    def test_normalize_diacritics(self):
        self.assertEqual(normalize("Mötley Crüe"), "mötley crüe")
        self.assertEqual(normalize("Señorita"), "señorita")
        self.assertEqual(normalize("Beyoncé"), "beyoncé")

    def test_normalize_multilingual(self):
        self.assertEqual(normalize("ਨਵਾਂ ਸੰਧੂ"), "ਨਵਾਂ ਸੰਧੂ")
        self.assertEqual(normalize("अरिजीत सिंह"), "अरिजीत सिंह")
        self.assertEqual(normalize("YOASOBI - 夜に駆ける"), "yoasobi 夜に駆ける")

    def test_words(self):
        self.assertEqual(words("Blinding Lights (Official Video)"), {"blinding", "lights", "official", "video"})
        self.assertEqual(words(""), set())

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("Artist / Track : Name?"), "Artist _ Track _ Name_")
        self.assertEqual(sanitize_filename("  Leading and trailing.  "), "Leading and trailing")
        self.assertEqual(sanitize_filename(""), "unnamed_track")

    def test_clean_title_and_artist(self):
        t1, a1 = clean_title_and_artist("Seedhe Maut - Namastute (Official Audio)", "Seedhe Maut - Topic")
        self.assertEqual(t1, "Namastute")
        self.assertEqual(a1, "Seedhe Maut")

        t2, a2 = clean_title_and_artist("PEW PEW! (Official Music Video)", "Rawal, Bharg, Ikka")
        self.assertEqual(t2, "PEW PEW!")
        self.assertEqual(a2, "Rawal, Bharg, Ikka")


if __name__ == "__main__":
    unittest.main()


