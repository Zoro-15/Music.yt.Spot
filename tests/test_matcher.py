import unittest
from downloader.matcher import similarity, artist_match, bad_candidate, score_candidate


class TestMatcher(unittest.TestCase):
    def test_similarity(self):
        self.assertEqual(similarity("Blinding Lights", "Blinding Lights"), 1.0)
        self.assertGreater(similarity("Starboy", "Starboy (Official Music Video)"), 0.6)
        self.assertLess(similarity("Song A", "Completely Different B"), 0.3)

    def test_artist_match(self):
        self.assertGreaterEqual(artist_match("The Weeknd", "Starboy", "The Weeknd - Topic"), 30)
        self.assertGreaterEqual(artist_match("Post Malone, Swae Lee", "Sunflower (Spider-Man)", "PostMaloneVEVO"), 15)
        self.assertEqual(artist_match("Unknown Artist", "Random Song", "Random Channel"), 0)

    def test_bad_candidate(self):
        self.assertTrue(bad_candidate("Song Name (Slowed + Reverb)"))
        self.assertTrue(bad_candidate("Song Name (Speed Up)"))
        self.assertTrue(bad_candidate("Song Name 8D Audio"))
        self.assertFalse(bad_candidate("Official Music Video"))

    def test_score_candidate(self):
        # Official topic channel match with good title & duration
        score = score_candidate(
            spotify_title="Unbothered",
            spotify_artists="Navaan Sandhu",
            yt_title="Unbothered",
            channel="Navaan Sandhu - Topic",
            candidate_duration=293,
            target_duration=293,
        )
        self.assertGreaterEqual(score, 85)

        # Wrong artist penalty (Jineewells instead of Navaan Sandhu)
        wrong_artist_score = score_candidate(
            spotify_title="Unbothered",
            spotify_artists="Navaan Sandhu",
            yt_title="Unbothered",
            channel="Jineewells - Topic",
            candidate_duration=152,
            target_duration=293,
        )
        self.assertLess(wrong_artist_score, 40)


if __name__ == "__main__":
    unittest.main()
