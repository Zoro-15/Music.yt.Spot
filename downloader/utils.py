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
def get_ytdlp_auth_args():
    """
    Returns authentication / player client arguments for yt-dlp.
    Checks for cookies.txt in project root, input/, or data/.
    If cookies.txt exists, passes --cookies.
    Otherwise passes --extractor-args youtube:player_client=ios,android,mweb to bypass YouTube bot checks.
    """
    for c_path in [BASE_DIR / "cookies.txt", INPUT_DIR / "cookies.txt", DATA_DIR / "cookies.txt"]:
        if c_path.exists() and c_path.is_file():
            return ["--cookies", str(c_path)]

    return ["--extractor-args", "youtube:player_client=ios,android,mweb"]


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


def clean_project_cache(include_output=False):
    """
    Clears generated playlist CSV, progress state, logs, temporary files, and __pycache__.
    If include_output is True, also clears the output directory.
    """
    print_banner("Cleaning Project Data & Cache")
    files_to_remove = [
        TRACKS_CSV,
        PROGRESS_FILE,
        FAILED_FILE,
        REVIEW_FILE,
        DATA_DIR / "downloaded_archive.txt",
    ]

    removed_count = 0
    for f in files_to_remove:
        if f.exists():
            try:
                f.unlink()
                print(f" ✓ Removed: {f.relative_to(BASE_DIR)}")
                removed_count += 1
            except Exception as e:
                print(f" ⚠ Could not remove {f.name}: {e}")

    # Remove temporary files in data/ and project root
    for pat in ["*.tmp", "*.temp", "*.part", "*.ytdl"]:
        for f in list(DATA_DIR.glob(pat)) + list(BASE_DIR.glob(pat)):
            if f.exists():
                try:
                    f.unlink()
                    removed_count += 1
                except Exception:
                    pass

    # Remove __pycache__ directories
    for pycache in BASE_DIR.rglob("__pycache__"):
        if pycache.exists() and pycache.is_dir():
            try:
                import shutil
                shutil.rmtree(pycache)
                print(f" ✓ Cleared cache: {pycache.relative_to(BASE_DIR)}")
            except Exception:
                pass

    if include_output and OUTPUT_DIR.exists():
        for item in OUTPUT_DIR.glob("*"):
            if item.name != ".gitkeep":
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                    removed_count += 1
                except Exception:
                    pass
        print(" ✓ Cleared output folder files")

    print(f"\nCleanup complete. Removed {removed_count} files/caches.")
    return True


