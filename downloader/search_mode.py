from downloader.config import load_config
from downloader.cover_art import fetch_high_res_cover
from downloader.ffmpeg_tagger import apply_native_metadata, crop_square_artwork
from downloader.lyrics import fetch_lyrics
from downloader.matcher import search_youtube
from downloader.utils import (
    OUTPUT_DIR,
    run_command,
    sanitize_filename,
    print_banner,
    sync_to_android_music,
    get_ytdlp_auth_args,
    get_audio_quality_args,
)


def search_and_download_song(query: str) -> bool:
    """Searches YouTube / YouTube Music by song name and downloads audio with metadata and lyrics."""
    if not query or not query.strip():
        print("ERROR: Please provide a song name or search query.")
        return False

    query = query.strip()
    print_banner(f"Searching Song: '{query}'")
    cfg = load_config()

    candidates, error = search_youtube(title=query, artists="", min_score=cfg.get("min_score", 50), use_ytmusic=cfg.get("ytmusic_priority", True))
    if error or not candidates:
        print(f"✖ Search failed: {error or 'No candidates found'}")
        return False

    best = candidates[0]
    print(f"Match: {best['title']} | Channel: {best['channel']} (Score: {best['score']})\n")

    safe_title = sanitize_filename(best["title"])
    output_template = str(OUTPUT_DIR / f"{safe_title}.%(ext)s")

    cmd = ["yt-dlp", "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--retry-sleep", "2", "--socket-timeout", "30", "--continue"] + get_audio_quality_args(cfg) + ["--add-metadata", "--embed-thumbnail", "--write-thumbnail", "--convert-thumbnails", "jpg"] + get_ytdlp_auth_args() + ["-o", output_template, best["url"]]
    code, stdout, stderr = run_command(cmd)


    if code != 0:
        print(f"✖ Download failed: {stderr[-1000:] if stderr else 'Unknown error'}")
        return False

    downloaded = list(OUTPUT_DIR.glob(f"{safe_title}.*"))
    audio_files = [p for p in downloaded if p.suffix.lower() in [".m4a", ".webm", ".opus", ".mp3", ".aac", ".flac"]]
    thumb_files = [p for p in downloaded if p.suffix.lower() in [".webp", ".jpg", ".jpeg", ".png"]]

    if not audio_files:
        print("✖ Download failed: Output audio file is missing")
        return False

    audio = audio_files[0]
    if audio.suffix.lower() == ".webm":
        opus_path = audio.with_suffix(".opus")
        r_code, _, _ = run_command(["ffmpeg", "-y", "-i", str(audio), "-c:a", "copy", str(opus_path)])
        if r_code == 0 and opus_path.exists():
            try:
                audio.unlink()
                audio = opus_path
            except Exception:
                pass

    if thumb_files and cfg.get("square_crop_artwork", True):
        crop_square_artwork(thumb_files[0])

    cover_bytes = fetch_high_res_cover(best["title"], best["channel"]) if cfg.get("fetch_high_res_cover", True) else None
    lyrics_text = None
    if cfg.get("fetch_lyrics", True):
        success, res, raw_lyrics = fetch_lyrics(best["title"], best["channel"], "", audio)
        if success:
            lyrics_text = raw_lyrics

    apply_native_metadata(audio, best["title"], best["channel"], "Single Search", image_bytes=cover_bytes, lyrics_text=lyrics_text if cfg.get("embed_lyrics", True) else None)
    if cfg.get("auto_sync_android_music", True):
        synced, _ = sync_to_android_music(audio)
        if synced:
            try:
                if audio.exists():
                    audio.unlink()
                for t in thumb_files:
                    if t.exists():
                        t.unlink()
            except Exception:
                pass

    print_banner(f"✓ SONG DOWNLOAD COMPLETE: {best['title']}")
    return True



