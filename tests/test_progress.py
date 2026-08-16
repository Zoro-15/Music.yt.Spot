import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from downloader.progress import reset_cache_and_failed_tracks, load_progress, save_progress, log_failed, log_review


class TestProgress(unittest.TestCase):
    def test_progress_load_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prog_file = Path(tmp_dir) / "progress.json"
            with patch("downloader.progress.PROGRESS_FILE", prog_file):
                save_progress({"1": {"title": "Test Song", "status": "success"}}, force=True)
                loaded = load_progress()
                self.assertIn("1", loaded)
                self.assertEqual(loaded["1"]["status"], "success")

    def test_reset_cache_and_failed_tracks_no_error(self):
        # Verifies that List and Path types are properly defined and don't raise NameError
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_dir = Path(tmp_dir)
            with patch("downloader.progress.DATA_DIR", dummy_dir), \
                 patch("downloader.progress.FAILED_FILE", dummy_dir / "failed.txt"), \
                 patch("downloader.progress.REVIEW_FILE", dummy_dir / "review.txt"), \
                 patch("downloader.progress.PROGRESS_FILE", dummy_dir / "progress.json"), \
                 patch("downloader.progress.TRACKS_CSV", dummy_dir / "tracks.csv"):
                res = reset_cache_and_failed_tracks()
                self.assertIsInstance(res, int)


if __name__ == "__main__":
    unittest.main()
