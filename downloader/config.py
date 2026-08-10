import json
from pathlib import Path
from downloader.utils import BASE_DIR

CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_CONFIG = {
    "max_workers": 8,
    "min_score": 70,
    "ytmusic_priority": True,
    "fetch_lyrics": True,
    "square_crop_artwork": True,
    "auto_sync_android_music": True,
    "include_index_in_filename": False,
}


def load_config():
    """Loads configuration settings from config.json or initializes default file."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        # Merge with defaults to ensure missing keys are populated
        merged = DEFAULT_CONFIG.copy()
        merged.update(user_cfg)
        return merged
    except Exception as e:
        print(f"WARNING: Could not parse config.json ({e}). Using defaults.")
        return DEFAULT_CONFIG.copy()


def save_config(cfg):
    """Saves configuration dict to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"WARNING: Could not write config.json: {e}")
