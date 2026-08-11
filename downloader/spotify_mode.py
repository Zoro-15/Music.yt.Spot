import csv
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Union, List

from downloader.config import load_config
from downloader.cover_art import fetch_high_res_cover
from downloader.finder import discover_playlist_json
from downloader.ffmpeg_tagger import apply_native_metadata, crop_square_artwork
from downloader.lyrics import fetch_lyrics
from downloader.matcher import search_youtube
from downloader.progress import load_progress, save_progress, log_failed, log_review
from downloader.spotify_api import fetch_spotify_metadata_from_url, parse_spotify_url
from downloader.utils import (
    TRACKS_CSV,
    OUTPUT_DIR,
    run_command,
    sanitize_filename,
    print_banner,
    sync_to_android_music,
    find_android_music_dir,
    get_ytdlp_auth_args,
    get_audio_quality_args,
    generate_m3u8_playlist,
)

# Rich library optional import for thread-safe UI
try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

progress_lock = threading.Lock()


def prepare_csv(source_input: Optional[Union[str, Path]] = None) -> bool:
    """Parses Exportify JSON file or direct Spotify URL and prepares data/tracks.csv."""
    print_banner("Preparing Spotify Playlist CSV")
    tracks_data: List[Dict[str, Any]] = []

    if isinstance(source_input, str) and ("spotify.com" in source_input or "spotify:" in source_input):
        print(f"Resolving Spotify URL: {source_input}")
        name, tracks_data = fetch_spotify_metadata_from_url(source_input)
        if not tracks_data:
            print("ERROR: Could not fetch track metadata from Spotify URL.")
            return False
        print(f" ✓ Successfully loaded: {name or 'Spotify Link'}")
    else:
        source_json = discover_playlist_json(source_input)
        if not source_json:
            print("\nERROR: No valid Exportify playlist JSON found or specified.")
            return False

        try:
            with open(source_json, "r", encoding="utf-8", errors="replace") as f:
                raw_data = json.load(f)
        except Exception as e:
            print(f"ERROR: Could not read JSON file: {e}")
            return False

        raw_tracks = raw_data if isinstance(raw_data, list) else (raw_data.get("items") or raw_data.get("tracks") or []) if isinstance(raw_data, dict) else []

        for track in raw_tracks:
            if not isinstance(track, dict):
                continue
            t_obj = track.get("track") if isinstance(track.get("track"), dict) else track
            title = (t_obj.get("name") or t_obj.get("title") or t_obj.get("track_name") or t_obj.get("Track Name") or "").strip()
            artists_data = t_obj.get("artists") or t_obj.get("artist") or t_obj.get("Artist Name(s)")
            artists = ", ".join((a.get("name") if isinstance(a, dict) else str(a)).strip() for a in artists_data if a) if isinstance(artists_data, list) else str(artists_data or "").strip()
            album_data = t_obj.get("album") or t_obj.get("Album Name")
            album = album_data.get("name", "").strip() if isinstance(album_data, dict) else str(album_data or "").strip()
            images = album_data.get("images") if isinstance(album_data, dict) else []
            cover_url = images[0].get("url", "") if images and isinstance(images, list) else ""
            dur_ms = t_obj.get("duration_ms") or t_obj.get("Duration (ms)") or t_obj.get("duration") or 0
            if title:
                tracks_data.append({"title": title, "artist": artists, "album": album, "duration_sec": int(dur_ms / 1000) if dur_ms else 0, "cover_url": cover_url})

    if not tracks_data:
        print("ERROR: Could not extract valid track items.")
        return False

    with open(TRACKS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "title", "artist", "album", "duration_sec", "cover_url"])
        for idx, item in enumerate(tracks_data, 1):
            writer.writerow([idx, item["title"], item["artist"], item.get("album", ""), item.get("duration_sec", 0), item.get("cover_url", "")])

    # Clear stale progress tracking when preparing a new playlist CSV
    from downloader.utils import PROGRESS_FILE
    if PROGRESS_FILE.exists():
        try:
            PROGRESS_FILE.unlink()
        except Exception:
            pass

    print(f"\n✓ Playlist prepared! {len(tracks_data)} tracks written to {TRACKS_CSV}\n")
    return True


def process_single_track(row: Dict[str, str], index: int, cfg: Dict[str, Any]) -> Tuple[str, Union[Dict[str, Any], str]]:
    """Processes YouTube search, score matching, yt-dlp download, Mutagen tagging, and Android sync."""
    title, artists, album = row["title"], row["artist"], row.get("album", "")
    target_duration_sec, cover_url = int(row.get("duration_sec") or 0), row.get("cover_url", "")
    min_score, use_ytmusic = cfg.get("min_score", 70), cfg.get("ytmusic_priority", True)

    safe_title = sanitize_filename(title)
    filename_with_idx = f"{index:03d} - {safe_title}"
    music_dir = find_android_music_dir()

    # Strictly check if this specific track file (indexed or exact title in output dir) exists
    for ext in [".m4a", ".opus", ".mp3", ".aac", ".flac"]:
        if (OUTPUT_DIR / f"{filename_with_idx}{ext}").exists() or (OUTPUT_DIR / f"{safe_title}{ext}").exists():
            return "success", {"title": title, "channel": "Local Disk", "score": 100}



    candidates, error = search_youtube(title, artists, min_score=min_score, use_ytmusic=use_ytmusic, target_duration_sec=target_duration_sec)
    if error or not candidates:
        return "failed", error or "No candidates"

    best = candidates[0]
    if best["score"] < min_score:
        with progress_lock:
            log_review(index, title, artists, best["score"], best["title"], best["url"])

    filename = f"{index:03d} - {safe_title}" if cfg.get("include_index_in_filename", False) else safe_title
    output_template = str(OUTPUT_DIR / f"{filename}.%(ext)s")
    audio_args = get_audio_quality_args(cfg)

    cmd = ["yt-dlp", "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--retry-sleep", "2", "--socket-timeout", "30", "--continue"] + audio_args + ["--add-metadata", "--write-thumbnail", "--embed-thumbnail"] + get_ytdlp_auth_args() + ["-o", output_template, best["url"]]
    code, stdout, stderr = run_command(cmd)

    if code != 0:
        fallback_cmd = ["yt-dlp", "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--retry-sleep", "2", "--socket-timeout", "30", "--continue"] + audio_args + ["--write-thumbnail"] + get_ytdlp_auth_args() + ["-o", output_template, best["url"]]
        code, stdout, stderr = run_command(fallback_cmd)

    if code != 0:
        return "failed", stderr.strip().splitlines()[-1] if stderr and stderr.strip() else "Unknown error"

    downloaded = list(OUTPUT_DIR.glob(f"{filename}.*"))
    audio_files = [p for p in downloaded if p.suffix.lower() in [".m4a", ".webm", ".opus", ".mp3", ".aac", ".flac"]]
    thumb_files = [p for p in downloaded if p.suffix.lower() in [".webp", ".jpg", ".jpeg", ".png"]]

    if not audio_files:
        return "failed", "yt-dlp completed but output audio file is missing"

    audio = audio_files[0]

    # Convert .webm (Opus) container to native .opus audio container losslessly (0 re-encoding)
    if audio.suffix.lower() == ".webm":
        opus_path = audio.with_suffix(".opus")
        remux_cmd = ["ffmpeg", "-y", "-i", str(audio), "-c:a", "copy", str(opus_path)]
        r_code, _, _ = run_command(remux_cmd)
        if r_code == 0 and opus_path.exists():
            try:
                audio.unlink()
                audio = opus_path
            except Exception:
                pass

    if thumb_files and cfg.get("square_crop_artwork", True):
        crop_square_artwork(thumb_files[0])

    cover_bytes = fetch_high_res_cover(title, artists, preferred_url=cover_url) if cfg.get("fetch_high_res_cover", True) else None
    lyrics_text = None
    if cfg.get("fetch_lyrics", True):
        success, res, raw_lyrics = fetch_lyrics(title, artists, album, audio)
        if success:
            lyrics_text = raw_lyrics
            if isinstance(res, Path) and cfg.get("auto_sync_android_music", True):
                sync_to_android_music(res)

    apply_native_metadata(audio, title, artists, album, image_bytes=cover_bytes, lyrics_text=lyrics_text if cfg.get("embed_lyrics", True) else None, track_number=index)
    if cfg.get("auto_sync_android_music", True):
        sync_to_android_music(audio)

    return "success", best



def download_single_spotify_track(row: Dict[str, str], index: int) -> Tuple[str, Union[Dict[str, Any], str]]:
    """Wrapper alias for processing a single Spotify track entry."""
    return process_single_track(row, index, load_config())


def run_download() -> None:
    """Main multi-threaded download runner for Spotify playlist tracks."""
    if not TRACKS_CSV.exists() and not prepare_csv():
        print("Aborting download.")
        return

    cfg = load_config()
    max_workers = cfg.get("max_workers", 10)

    tracks = []
    with open(TRACKS_CSV, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tracks.append(row)

    progress = load_progress()
    pending = [r for r in tracks if progress.get(str(r["index"]), {}).get("status") != "success"]

    if not pending:
        print("\nAll tracks are already completed!")
        all_audios = list(OUTPUT_DIR.glob("*.*"))
        generate_m3u8_playlist("Spotify Playlist", all_audios)
        print_banner("PLAYLIST PROCESSING COMPLETE")
        return

    print_banner(f"Downloading {len(pending)} Tracks ({max_workers}x Threads)")

    if RICH_AVAILABLE:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as prg:
            task = prg.add_task("Downloading tracks...", total=len(pending))

            def worker_task(row: Dict[str, str]) -> None:
                idx = int(row["index"])
                status, result = process_single_track(row, idx, cfg)
                with progress_lock:
                    key = str(idx)
                    progress[key] = {"title": row["title"], "artist": row["artist"], "album": row.get("album", ""), "status": status}
                    if isinstance(result, dict):
                        progress[key].update({"youtube_title": result.get("title"), "youtube_channel": result.get("channel"), "youtube_url": result.get("url"), "score": result.get("score")})
                    save_progress(progress)
                    if status == "failed":
                        log_failed(idx, row["title"], row["artist"], str(result))
                    elif status == "review" and isinstance(result, dict):
                        log_review(idx, row["title"], row["artist"], result.get("score"), result.get("title"), result.get("url"))
                    prg.advance(task)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(worker_task, r) for r in pending]
                for f in as_completed(futures):
                    try:
                        f.result()
                    except Exception as e:
                        pass
    else:
        def worker_task(row: Dict[str, str]) -> None:
            idx = int(row["index"])
            status, result = process_single_track(row, idx, cfg)
            with progress_lock:
                key = str(idx)
                progress[key] = {"title": row["title"], "artist": row["artist"], "album": row.get("album", ""), "status": status}
                if isinstance(result, dict):
                    progress[key].update({"youtube_title": result.get("title"), "youtube_channel": result.get("channel"), "youtube_url": result.get("url"), "score": result.get("score")})
                save_progress(progress)
                if status == "failed":
                    log_failed(idx, row["title"], row["artist"], str(result))
                elif status == "review" and isinstance(result, dict):
                    log_review(idx, row["title"], row["artist"], result.get("score"), result.get("title"), result.get("url"))
                print(f"[{idx:03d}] {status.upper()}: '{row['title']}'")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker_task, r) for r in pending]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    pass

    # Auto-generate .m3u8 playlist file
    all_audios = list(OUTPUT_DIR.glob("*.*"))
    generate_m3u8_playlist("Spotify Playlist", all_audios)
    print_banner("PLAYLIST PROCESSING COMPLETE")

