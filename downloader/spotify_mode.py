import csv
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from downloader.config import load_config
from downloader.finder import discover_playlist_json
from downloader.ffmpeg_tagger import apply_spotify_metadata, crop_square_artwork
from downloader.lyrics import fetch_lyrics
from downloader.matcher import search_youtube
from downloader.progress import load_progress, save_progress, log_failed, log_review
from downloader.utils import (
    TRACKS_CSV,
    OUTPUT_DIR,
    run_command,
    sanitize_filename,
    print_banner,
    sync_to_android_music,
)

# Thread-safety lock for writing progress state and logs
progress_lock = threading.Lock()


def prepare_csv(json_path=None):
    """
    Parses Exportify JSON file and prepares data/tracks.csv.
    """
    print_banner("Preparing Spotify Playlist CSV")

    source_json = discover_playlist_json(json_path)
    if not source_json:
        print("\nERROR: No valid Exportify playlist JSON found.")
        print("Please export your Spotify playlist via Exportify and place the JSON in input/.")
        return False

    print(f"Reading: {source_json.name}")

    try:
        with open(source_json, "r", encoding="utf-8", errors="replace") as f:
            tracks = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not read JSON file: {e}")
        return False

    if not isinstance(tracks, list):
        print("ERROR: Unsupported JSON format. Expected a list of Spotify track objects.")
        return False

    valid_count = 0
    with open(TRACKS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "title", "artist", "album"])

        for index, track in enumerate(tracks, 1):
            title = track.get("name", "").strip()
            artists = ", ".join(
                artist.get("name", "").strip()
                for artist in track.get("artists", [])
                if artist.get("name")
            )
            album = track.get("album", "").strip()

            if not title:
                continue

            writer.writerow([index, title, artists, album])
            valid_count += 1

    print("\n" + "=" * 50)
    print("Playlist prepared successfully!")
    print("=" * 50)
    print(f" Tracks found : {len(tracks)}")
    print(f" Valid tracks : {valid_count}")
    print(f" CSV created  : {TRACKS_CSV}")
    print("=" * 50 + "\n")
    return True


def process_single_track(row, index, cfg):
    """
    Processes YouTube search, score matching, yt-dlp download, FFmpeg tagging,
    artwork cropping, lyrics fetching, and Android sync for a single Spotify track.
    """
    title = row["title"]
    artists = row["artist"]
    album = row["album"]
    min_score = cfg.get("min_score", 70)
    use_ytmusic = cfg.get("ytmusic_priority", True)

    print(f"[{index:03d}] Processing: '{title}' by {artists}")

    candidates, error = search_youtube(
        title, artists, min_score=min_score, use_ytmusic=use_ytmusic
    )

    if error or not candidates:
        print(f"[{index:03d}] ✖ Search failed: {error or 'No candidates'}")
        return "failed", error or "No candidates"

    best = candidates[0]

    if best["score"] < min_score:
        print(f"[{index:03d}] ⚠ Low confidence match ({best['score']} < {min_score}) -> Review")
        return "review", best

    safe_title = sanitize_filename(title)
    if cfg.get("include_index_in_filename", False):
        filename = f"{index:03d} - {safe_title}"
    else:
        filename = safe_title
    output_template = str(OUTPUT_DIR / f"{filename}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--retries", "5",
        "--fragment-retries", "5",
        "--retry-sleep", "2",
        "--socket-timeout", "30",
        "--continue",
        # Native audio priority: M4A/AAC > WebM/Opus > best audio
        "-f", "ba[ext=m4a]/ba[ext=webm]/ba",
        "--add-metadata",
        "--embed-thumbnail",
        "--write-thumbnail",
        "-o", output_template,
        best["url"],
    ]

    code, stdout, stderr = run_command(cmd)

    if code != 0:
        print(f"[{index:03d}] ✖ Download failed")
        return "failed", stderr

    # Locate downloaded media files
    downloaded = list(OUTPUT_DIR.glob(f"{filename}.*"))
    audio_files = [
        p for p in downloaded
        if p.suffix.lower() in [".m4a", ".webm", ".opus", ".mp3", ".aac"]
    ]
    thumb_files = [
        p for p in downloaded
        if p.suffix.lower() in [".webp", ".jpg", ".jpeg", ".png"]
    ]

    if audio_files:
        audio = audio_files[0]

        # 1. Apply lossless Spotify metadata
        apply_spotify_metadata(audio, title, artists, album)

        # 2. Crop artwork to 1:1 square if thumbnail downloaded & enabled in config
        if thumb_files and cfg.get("square_crop_artwork", True):
            crop_square_artwork(thumb_files[0])

        # 3. Fetch LRCLIB synced lyrics if enabled
        if cfg.get("fetch_lyrics", True):
            fetch_lyrics(title, artists, album, audio)

        # 4. Sync to Android System Music folder if enabled
        if cfg.get("auto_sync_android_music", True):
            sync_to_android_music(audio)

    print(f"[{index:03d}] ✓ Finished successfully: {best['title']} (Score: {best['score']})")
    return "success", best


def download_single_spotify_track(row, index):
    """
    Wrapper alias for processing a single Spotify track entry.
    """
    cfg = load_config()
    return process_single_track(row, index, cfg)


def run_download():
    """
    Main multi-threaded download runner for Spotify playlist tracks.
    Reads max_workers (default 5) from config.json.
    """
    if not TRACKS_CSV.exists():
        print("ERROR: data/tracks.csv not found.")
        print("Running prepare.py automatically...")
        if not prepare_csv():
            print("Aborting download.")
            return

    cfg = load_config()
    max_workers = cfg.get("max_workers", 5)

    tracks = []
    with open(TRACKS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tracks.append(row)

    print_banner(f"Starting Download Loop — {len(tracks)} Tracks ({max_workers}x Parallel Workers)")
    progress = load_progress()

    pending_tracks = []
    for row in tracks:
        index = int(row["index"])
        key = str(index)
        if progress.get(key, {}).get("status") == "success":
            print(f"[{index:03d}] '{row['title']}' already completed. Skipping.")
            continue
        pending_tracks.append((row, index))

    if not pending_tracks:
        print("\nAll tracks are already completed!")
        print_banner("PLAYLIST PROCESSING COMPLETE")
        return

    print(f"\nProcessing {len(pending_tracks)} remaining tracks with {max_workers} concurrent threads...\n")

    def worker_task(item):
        row, index = item
        status, result = process_single_track(row, index, cfg)
        key = str(index)

        with progress_lock:
            progress[key] = {
                "title": row["title"],
                "artist": row["artist"],
                "album": row["album"],
                "status": status,
            }
            if isinstance(result, dict):
                progress[key]["youtube_title"] = result.get("title")
                progress[key]["youtube_channel"] = result.get("channel")
                progress[key]["youtube_url"] = result.get("url")
                progress[key]["score"] = result.get("score")

            save_progress(progress)

            if status == "failed":
                log_failed(index, row["title"], row["artist"], result if isinstance(result, str) else "Failed download")
            elif status == "review" and isinstance(result, dict):
                log_review(index, row["title"], row["artist"], result.get("score"), result.get("title"), result.get("url"))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker_task, item) for item in pending_tracks]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Worker exception: {e}")

    print_banner("PLAYLIST PROCESSING COMPLETE")
