import os
import re
import subprocess
from pathlib import Path

# ============================================================
# PROJECT DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "input"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

TRACKS_CSV = DATA_DIR / "tracks.csv"
PROGRESS_FILE = DATA_DIR / "progress.json"
FAILED_FILE = DATA_DIR / "failed.txt"
REVIEW_FILE = DATA_DIR / "review.txt"

# Ensure core directories exist
INPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SUBPROCESS HELPER
# ============================================================

def run_command(cmd, cwd=None):
    """
    Executes a shell command via subprocess and returns (returncode, stdout, stderr).
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


# ============================================================
# TEXT HELPERS & SANITIZATION
# ============================================================

def normalize(text):
    """
    Normalizes string by lowercasing, converting non-word characters to spaces,
    and stripping extra whitespace.
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def words(text):
    """Returns a set of normalized unique words."""
    norm = normalize(text)
    return set(norm.split()) if norm else set()


def sanitize_filename(name):
    """
    Sanitizes string to be a valid, cross-platform filename (Android / Linux / Windows).
    Removes invalid characters (< > : " / \\ | ? * \\x00-\\x1f) and trims dots/spaces.
    """
    if not name:
        return "unnamed_track"
    # Replace illegal characters with underscore
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name))
    # Replace multiple underscores/spaces
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    # Strip trailing periods/spaces which Windows/Android dislike
    sanitized = sanitized.rstrip(". ")
    return sanitized if sanitized else "unnamed_track"


def print_banner(text):
    """Prints a styled banner for terminal UI."""
    width = 70
    print()
    print("=" * width)
    print(f" {text}")
    print("=" * width)
    print()


# ============================================================
# ANDROID MUSIC SYSTEM INTEGRATION
# ============================================================

def find_android_music_dir():
    """Returns candidate Android system Music folder path if available."""
    home = Path.home()
    candidates = [
        home / "storage" / "music",
        home / "storage" / "shared" / "Music",
        Path("/sdcard/Music"),
        Path("/storage/emulated/0/Music"),
    ]
    for d in candidates:
        if d.exists() and d.is_dir():
            return d
    return None


def sync_to_android_music(file_path):
    """
    Copies completed audio / thumbnail / lyrics files to the Android system Music folder.
    """
    music_dir = find_android_music_dir()
    if not music_dir or not file_path.exists():
        return False, "Android Music directory not found"

    try:
        dest = music_dir / file_path.name
        import shutil
        shutil.copy2(file_path, dest)
        trigger_android_media_scanner(dest)
        return True, f"Synced to Android Music: {dest.name}"
    except Exception as e:
        return False, f"Could not sync to Music folder: {e}"


def trigger_android_media_scanner(file_path):
    """Triggers Android system media scanner broadcast so music player apps detect new songs."""
    cmd = [
        "am", "broadcast",
        "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", f"file://{file_path.resolve()}"
    ]
    run_command(cmd)

