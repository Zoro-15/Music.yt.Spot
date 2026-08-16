import csv
import json
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
from downloader.utils import (
    PROGRESS_FILE,
    TRACKS_CSV,
    FAILED_FILE,
    REVIEW_FILE,
    DATA_DIR,
    OUTPUT_DIR,
    BASE_DIR,
    find_android_music_dir,
    print_banner,
    sanitize_filename,
)


def load_progress() -> Dict[str, Dict[str, Any]]:
    """Loads current progress state from data/progress.json."""
    if not PROGRESS_FILE.exists():
        return {}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_last_save_time = 0.0


def save_progress(progress: Dict[str, Dict[str, Any]], force: bool = False) -> None:
    """Saves progress atomically to data/progress.json with time throttling."""
    global _last_save_time
    import time
    now = time.time()
    if not force and (now - _last_save_time < 0.5):
        return
    _last_save_time = now

    tmp = PROGRESS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        tmp.replace(PROGRESS_FILE)
    except Exception:
        pass


def log_failed(index: Union[int, str], title: str, artist: str, reason: str) -> None:
    """Logs a failed track to data/failed.txt."""
    try:
        with open(FAILED_FILE, "a", encoding="utf-8") as f:
            f.write(f"{index}\t{title}\t{artist}\t{reason}\n")
    except Exception:
        pass


def log_review(index: Union[int, str], title: str, artist: str, score: Union[int, str], yt_title: str, url: str) -> None:
    """Logs a low-confidence track to data/review.txt."""
    try:
        with open(REVIEW_FILE, "a", encoding="utf-8") as f:
            f.write(f"{index}\t{title}\t{artist}\t{score}\t{yt_title}\t{url}\n")
    except Exception:
        pass


def show_status() -> None:
    """Prints a clear summary report of current downloading progress."""
    total = sum(1 for _ in csv.DictReader(open(TRACKS_CSV, "r", encoding="utf-8"))) if TRACKS_CSV.exists() else 0
    progress = load_progress()
    success = sum(1 for x in progress.values() if x.get("status") == "success")
    failed = sum(1 for x in progress.values() if x.get("status") == "failed")
    review = sum(1 for x in progress.values() if x.get("status") == "review")
    processed = success + failed + review

    print(f"\nStatus Report\n{'='*45}\n Total tracks : {total}\n Processed    : {processed} (Success: {success}, Failed: {failed}, Review: {review})\n Remaining    : {max(0, total - processed)}\n{'='*45}")

    if failed > 0:
        print("\n  Failure Reasons Breakdown:")
        reasons_summary: Dict[str, int] = {}
        for item in progress.values():
            if item.get("status") == "failed":
                r = item.get("reason", "Unknown failure")
                reasons_summary[r] = reasons_summary.get(r, 0) + 1
        for r_text, count in reasons_summary.items():
            print(f"   • {count} track(s): {r_text}")
        print("  👉 Check data/failed.txt for full details.")
    print()


def extract_artist_tag(audio_obj: Any) -> str:
    """Extracts artist tag string from Mutagen audio object."""
    if audio_obj is None:
        return ""
    try:
        if hasattr(audio_obj, "get"):
            if "©ART" in audio_obj:
                val = audio_obj["©ART"]
                return val[0] if isinstance(val, list) and val else str(val)
            if "ARTIST" in audio_obj:
                val = audio_obj["ARTIST"]
                return val[0] if isinstance(val, list) and val else str(val)
        if hasattr(audio_obj, "tags") and audio_obj.tags:
            tpe1 = audio_obj.tags.get("TPE1")
            if tpe1:
                return str(tpe1.text[0]) if hasattr(tpe1, "text") and tpe1.text else str(tpe1)
    except Exception:
        pass
    return ""


def reset_cache_and_failed_tracks() -> int:
    """
    Clears search cache, failed track logs, and syncs progress.json with physical files on disk.
    Tracks that are not physically present in the Android Music folder or output directory
    are reset in the progress state so they will be downloaded when selecting Option 1.
    Does NOT delete any existing music files.
    """
    print_banner("Resetting Cache & Syncing Missing Tracks")

    # 1. Remove failed and review log files
    for f in [FAILED_FILE, REVIEW_FILE, DATA_DIR / "search_cache.json"]:
        if f.exists():
            try:
                f.unlink()
                print(f" ✓ Cleared: {f.name}")
            except Exception:
                pass

    # 2. Clear output/ directory completely to prevent stale files
    if OUTPUT_DIR.exists():
        for item in OUTPUT_DIR.glob("*"):
            if item.name != ".gitkeep":
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                except Exception:
                    pass
        print(" ✓ Cleared output folder files")

    # 3. Clear temporary download parts
    for pat in ["*.tmp", "*.temp", "*.part", "*.ytdl"]:
        for f in list(DATA_DIR.glob(pat)) + list(OUTPUT_DIR.glob(pat)):
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

    # 4. Synchronize progress.json strictly against physical Android Music folder
    progress = load_progress()
    music_dir = find_android_music_dir()
    search_dirs: List[Path] = []
    if music_dir and music_dir.exists() and music_dir.is_dir():
        search_dirs.append(music_dir)
        try:
            for sub in music_dir.iterdir():
                if sub.is_dir():
                    search_dirs.append(sub)
        except Exception:
            pass

    target_map: Dict[str, Dict[str, Any]] = {}
    if TRACKS_CSV.exists():
        with open(TRACKS_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                target_map[str(row["index"])] = row

    reset_count = 0
    verified_count = 0

    if target_map:
        new_progress = {}
        for idx, target in target_map.items():
            safe_title = sanitize_filename(target["title"])
            filename_with_idx = f"{int(idx):03d} - {safe_title}"

            found = False
            for d in search_dirs:
                for ext in [".m4a", ".opus", ".mp3", ".aac", ".flac"]:
                    p1 = d / f"{filename_with_idx}{ext}"
                    p2 = d / f"{safe_title}{ext}"
                    if (p1.exists() and p1.is_file() and p1.stat().st_size > 1000) or (p2.exists() and p2.is_file() and p2.stat().st_size > 1000):
                        found = True
                        break
                if found:
                    break

            if found and idx in progress and progress[idx].get("status") == "success":
                new_progress[idx] = progress[idx]
                verified_count += 1
            else:
                reset_count += 1

        save_progress(new_progress, force=True)
    else:
        if PROGRESS_FILE.exists():
            try:
                PROGRESS_FILE.unlink()
            except Exception:
                pass

    print(f"\n ✓ Verified {verified_count} completed track(s) present in Music folder.")
    print(f" ✓ Reset {reset_count} missing/failed track(s) in download queue.")
    print("\n👉 Done! You can now select Option 1 in the Main Menu to download all missing tracks.")
    return reset_count


