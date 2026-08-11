import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Set, Dict, Any

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

def run_command(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
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


def find_downloads_dirs() -> List[Path]:
    """
    Returns candidate download paths for Termux / Android.
    """
    home = Path.home()
    candidates = [
        home / "storage" / "downloads",
        home / "storage" / "shared" / "Download",
        Path("/sdcard/Download"),
        Path("/storage/emulated/0/Download"),
    ]
    return [d for d in candidates if d.exists() and d.is_dir()]


def get_ytdlp_auth_args() -> List[str]:
    """
    Returns authentication / player client arguments for yt-dlp.
    Auto-discovers cookies.txt in project root, input/, data/, or Android Downloads folders.
    Otherwise uses Android YouTube app User-Agent + player_client=android_vr,web_creator to bypass YouTube bot checks.
    """
    # 1. Search project directories for any *cookie*.txt file
    for p_dir in [BASE_DIR, INPUT_DIR, DATA_DIR]:
        try:
            found = [f for f in p_dir.glob("*.txt") if "cookie" in f.name.lower()]
            if found:
                return ["--cookies", str(found[0])]
        except Exception:
            pass

    # 2. Search Android Downloads folders for any *cookie*.txt file
    for d_dir in find_downloads_dirs():
        try:
            found_cookies = [f for f in d_dir.glob("*.txt") if "cookie" in f.name.lower()]
            if found_cookies:
                selected_cookie = found_cookies[0]
                dest = DATA_DIR / "cookies.txt"
                try:
                    import shutil
                    shutil.copy2(selected_cookie, dest)
                    print(f" ✓ Auto-discovered cookies in Downloads: {selected_cookie.name}")
                    return ["--cookies", str(dest)]
                except Exception:
                    return ["--cookies", str(selected_cookie)]
        except Exception:
            pass

    # 3. Android VR & Web Creator Player Client (Zero Bot-Check Client)
    return [
        "--user-agent", "Mozilla/5.0 (Android 14; VR; Oculus Quest 2) AppleWebKit/537.36",
        "--extractor-args", "youtube:player_client=android_vr,web_creator,mweb"
    ]


# ============================================================
# TEXT HELPERS & SANITIZATION
# ============================================================

def normalize(text: str) -> str:
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


def words(text: str) -> Set[str]:
    """Returns a set of normalized unique words."""
    norm = normalize(text)
    return set(norm.split()) if norm else set()


def sanitize_filename(name: str) -> str:
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


def print_banner(text: str) -> None:
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

def find_android_music_dir() -> Optional[Path]:
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


def trigger_android_media_scanner(file_path: Path) -> bool:
    """
    Triggers Android MediaScanner broadcast to index new music files immediately.
    """
    if not file_path.exists():
        return False
    try:
        cmd = [
            "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{file_path.resolve()}"
        ]
        code, _, _ = run_command(cmd)
        return code == 0
    except Exception:
        return False


def sync_to_android_music(file_path: Path) -> Tuple[bool, str]:
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


def clean_project_cache(include_output: bool = False) -> bool:
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



