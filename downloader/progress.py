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


def audit_and_fix_mismatched_tracks(force_delete: bool = True, reset_failed: bool = True) -> int:
    """
    Audits existing downloaded tracks in output/ directory against target durations in tracks.csv.
    Removes wrong/mismatched audio files and resets failed tracks so they can all be re-downloaded correctly.
    """
    from downloader.utils import OUTPUT_DIR, print_banner, sanitize_filename
    from pathlib import Path

    if not TRACKS_CSV.exists():
        print("No tracks.csv found to audit. Please prepare a playlist CSV first.")
        return 0

    print_banner("Auditing Folder for Wrong Songs & Resetting Failed Tracks")

    target_map: Dict[str, Dict[str, Any]] = {}
    with open(TRACKS_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            target_map[str(row["index"])] = row

    progress = load_progress()
    mismatched_count = 0
    failed_reset_count = 0

    # 1. Reset failed tracks for re-download retry
    if reset_failed:
        failed_keys = [k for k, v in progress.items() if v.get("status") == "failed"]
        for k in failed_keys:
            del progress[k]
            failed_reset_count += 1
        if failed_reset_count > 0:
            print(f" ✓ Reset {failed_reset_count} previously failed track(s) for download retry.")

    try:
        import mutagen
    except ImportError:
        mutagen = None

    for idx, target in target_map.items():
        title = target["title"]
        target_dur = int(target.get("duration_sec") or 0)
        safe_title = sanitize_filename(title)
        filename_with_idx = f"{int(idx):03d} - {safe_title}"

        # Find file in output/
        found_file: Optional[Path] = None
        for ext in [".m4a", ".opus", ".mp3", ".aac", ".flac"]:
            p1 = OUTPUT_DIR / f"{filename_with_idx}{ext}"
            p2 = OUTPUT_DIR / f"{safe_title}{ext}"
            if p1.exists():
                found_file = p1
                break
            elif p2.exists():
                found_file = p2
                break

        if not found_file or not found_file.exists():
            continue

        is_mismatch = False
        reason = ""

        # Audit 1: Check actual audio duration if target_dur is available
        if target_dur > 0 and mutagen is not None:
            try:
                audio_info = mutagen.File(found_file)
                if audio_info and hasattr(audio_info, "info") and hasattr(audio_info.info, "length"):
                    actual_dur = int(audio_info.info.length)
                    diff = abs(actual_dur - target_dur)
                    if diff > 30 or (diff / max(target_dur, 1)) > 0.2:
                        is_mismatch = True
                        reason = f"Duration mismatch (File: {actual_dur // 60}:{actual_dur % 60:02d}, Target: {target_dur // 60}:{target_dur % 60:02d})"
            except Exception:
                pass

        # Audit 2: Check if marked as review/low score in progress
        if not is_mismatch and idx in progress:
            p_status = progress[idx].get("status")
            score = progress[idx].get("score") or 100
            if p_status == "review" or score < 60:
                is_mismatch = True
                reason = f"Low confidence match score ({score}/100)"

        if is_mismatch:
            mismatched_count += 1
            print(f" ⚠️ Flagged Track #{idx} '{title}': {reason}")
            if force_delete:
                try:
                    found_file.unlink()
                    print(f"    ✓ Removed wrong file: {found_file.name}")
                except Exception as e:
                    print(f"    ✖ Could not remove {found_file.name}: {e}")

                if idx in progress:
                    del progress[idx]

    total_reset = mismatched_count + failed_reset_count
    if total_reset > 0:
        save_progress(progress, force=True)

    print(f"\nAudit complete. Reset {total_reset} track(s) total ({mismatched_count} wrong files removed, {failed_reset_count} failed tracks reset).")
    return total_reset


