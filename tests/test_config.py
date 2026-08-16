import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from downloader.config import load_config, save_config, update_config_key, DEFAULT_CONFIG


class TestConfig(unittest.TestCase):
    def test_load_config_defaults(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_cfg_file = Path(tmp_dir) / "config.json"
            with patch("downloader.config.CONFIG_FILE", test_cfg_file):
                cfg = load_config()
                self.assertEqual(cfg["max_workers"], 10)
                self.assertEqual(cfg["audio_format"], "best_native")
                self.assertTrue(test_cfg_file.exists())

    def test_update_config_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_cfg_file = Path(tmp_dir) / "config.json"
            with patch("downloader.config.CONFIG_FILE", test_cfg_file):
                update_config_key("max_workers", 5)
                cfg = load_config()
                self.assertEqual(cfg["max_workers"], 5)


if __name__ == "__main__":
    unittest.main()
