import csv
import json
from typing import Dict, Any, Union
from downloader.utils import PROGRESS_FILE, TRACKS_CSV, FAILED_FILE, REVIEW_FILE


def load_progress() -> Dict[str, Dict[str, Any]]:
    """Loads current progress state from data/progress.json."""
    if not PROGRESS_FILE.exists():
        return {}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_progress(progress: Dict[str, Dict[str, Any]]) -> None:
    """Saves progress atomically to data/progress.json."""
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        tmp.replace(PROGRESS_FILE)
    except Exception as e:
        print(f"WARNING: Could not save progress state: {e}")


def log_failed(index: Union[int, str], title: str, artist: str, reason: str) -> None:
    """Logs a failed track to data/failed.txt."""
    try:
        with open(FAILED_FILE, "a", encoding="utf-8") as f:
            f.write(f"{index}\t{title}\t{artist}\t{reason}\n")
    except Exception as e:
        print(f"WARNING: Could not write to failed.txt: {e}")


def log_review(index: Union[int, str], title: str, artist: str, score: Union[int, str], yt_title: str, url: str) -> None:
    """Logs a low-confidence track to data/review.txt."""
    try:
        with open(REVIEW_FILE, "a", encoding="utf-8") as f:
            f.write(f"{index}\t{title}\t{artist}\t{score}\t{yt_title}\t{url}\n")
    except Exception as e:
        print(f"WARNING: Could not write to review.txt: {e}")


def show_status() -> None:
    """Prints a clear summary report of current downloading progress."""
    total = 0
    if TRACKS_CSV.exists():
        with open(TRACKS_CSV, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            total = sum(1 for _ in reader)

    progress = load_progress()

    success = sum(1 for x in progress.values() if x.get("status") == "success")
    failed = sum(1 for x in progress.values() if x.get("status") == "failed")
    review = sum(1 for x in progress.values() if x.get("status") == "review")

    processed = success + failed + review
    remaining = max(0, total - processed) if total > 0 else 0

    print()
    print("Spotify → yt-dlp Audio Downloader Status")
    print("=" * 40)
    print(f" Total tracks in CSV : {total}")
    print(f" Processed tracks   : {processed}")
    print(f"  ├─ Success        : {success}")
    print(f"  ├─ Failed         : {failed}")
    print(f"  └─ Needs Review   : {review}")
    print(f" Remaining tracks   : {remaining}")
    print("=" * 40)
    print()

