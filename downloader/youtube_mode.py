from downloader.config import load_config
from downloader.ffmpeg_tagger import crop_square_artwork
from downloader.utils import (
    OUTPUT_DIR,
    DATA_DIR,
    run_command,
    print_banner,
    sync_to_android_music,
    get_ytdlp_auth_args,
    get_audio_quality_args,
    generate_m3u8_playlist,
)


def download_from_link(url: str) -> bool:
    """Universal link downloader for Spotify, YouTube, and YT Music."""
    if not url or not url.strip():
        print("ERROR: Please provide a valid URL.")
        return False
    url = url.strip()
    if "spotify.com" in url or "spotify:" in url:
        from downloader.spotify_mode import prepare_csv, run_download
        print_banner("Spotify Direct URL Downloader Mode")
        if prepare_csv(url):
            run_download()
            return True
        return False

    return download_youtube_playlist(url) if ("list=" in url or "/playlist" in url or "/album" in url) else download_youtube_video(url)


def download_youtube_playlist(url: str) -> bool:
    """Downloads a complete YouTube or YT Music playlist/album directly using yt-dlp."""
    import json
    cfg = load_config()
    print_banner("Playlist / Album Downloader Mode")
    archive_file = DATA_DIR / "downloaded_archive.txt"
    output_template = str(OUTPUT_DIR / "%(playlist_index)03d - %(title)s.%(ext)s")
    before_files = set(OUTPUT_DIR.glob("*.*"))

    # Normalize YT Music URLs to standard www.youtube.com video list playlist URLs
    clean_url = url.strip().replace("music.youtube.com", "www.youtube.com").replace("youtube.com", "www.youtube.com").replace("www.www.youtube.com", "www.youtube.com")
    if "list=OLAK5uy_" in clean_url:
        clean_url = clean_url.replace("list=OLAK5uy_", "list=VLOLAK5uy_")
    elif "list=olAK5uy_" in clean_url:
        clean_url = clean_url.replace("list=olAK5uy_", "list=VLOLAK5uy_")

    cmd = [
        "yt-dlp",
        "--yes-playlist",
        "--download-archive", str(archive_file),
        "--retries", "5",
        "--fragment-retries", "5",
        "--retry-sleep", "2",
        "--socket-timeout", "30",
        "--continue",
        "--extractor-args", "youtube:player_client=android,web",
    ] + get_audio_quality_args(cfg) + ["--write-thumbnail", "--convert-thumbnails", "jpg"] + get_ytdlp_auth_args() + ["-o", output_template, clean_url]

    code, stdout, stderr = run_command(cmd)

    # Fallback: Extract video entries individually if playlist extraction encountered issues
    if code != 0:
        print("  Notice: Retrying playlist download using flat-playlist track resolution...")
        flat_cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", clean_url]
        f_code, f_stdout, _ = run_command(flat_cmd)

        video_urls = []
        if f_code == 0 and f_stdout.strip():
            try:
                entries = (json.loads(f_stdout) or {}).get("entries") or []
                for e in entries:
                    if e and isinstance(e, dict) and e.get("id"):
                        video_urls.append(f"https://www.youtube.com/watch?v={e['id']}")
            except Exception:
                pass

        if video_urls:
            print(f"  ✓ Extracted {len(video_urls)} track(s) from album playlist. Downloading...")
            success_count = 0
            for idx, v_url in enumerate(video_urls, 1):
                v_template = str(OUTPUT_DIR / f"{idx:03d} - %(title)s.%(ext)s")
                v_cmd = ["yt-dlp", "--no-playlist", "--retries", "3", "--socket-timeout", "20"] + get_audio_quality_args(cfg) + ["--write-thumbnail", "--convert-thumbnails", "jpg"] + get_ytdlp_auth_args() + ["-o", v_template, v_url]
                v_code, _, _ = run_command(v_cmd)
                if v_code == 0:
                    success_count += 1
            if success_count > 0:
                code = 0

    if code == 0:
        new_files = set(OUTPUT_DIR.glob("*.*")) - before_files
        for f in new_files:
            if f.suffix.lower() in [".webp", ".jpg", ".jpeg"] and cfg.get("square_crop_artwork", True):
                crop_square_artwork(f)
            elif f.suffix.lower() in [".m4a", ".webm", ".opus", ".mp3", ".aac", ".flac"]:
                target_f = f
                if f.suffix.lower() == ".webm":
                    opus_path = f.with_suffix(".opus")
                    r_code, _, _ = run_command(["ffmpeg", "-y", "-i", str(f), "-c:a", "copy", str(opus_path)])
                    if r_code == 0 and opus_path.exists():
                        try:
                            f.unlink()
                            target_f = opus_path
                        except Exception:
                            pass
                if cfg.get("auto_sync_android_music", True):
                    sync_to_android_music(target_f)

        generate_m3u8_playlist("YouTube Playlist", list(OUTPUT_DIR.glob("*.*")))
        print_banner("PLAYLIST / ALBUM DOWNLOAD COMPLETE")
        return True
    print(f"\nERROR: Download encountered issues: {stderr[-1000:] if stderr else 'Unknown failure'}")
    return False


def download_youtube_video(url: str) -> bool:
    """Downloads a single YouTube or YT Music video audio file natively."""
    cfg = load_config()
    print_banner("Single Audio / Music Video Downloader Mode")
    output_template = str(OUTPUT_DIR / "%(title)s.%(ext)s")
    before_files = set(OUTPUT_DIR.glob("*.*"))

    cmd = ["yt-dlp", "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--retry-sleep", "2", "--socket-timeout", "30", "--continue"] + get_audio_quality_args(cfg) + ["--write-thumbnail", "--convert-thumbnails", "jpg"] + get_ytdlp_auth_args() + ["-o", output_template, url]

    code, stdout, stderr = run_command(cmd)

    if code == 0:
        new_files = list(set(OUTPUT_DIR.glob("*.*")) - before_files)
        from downloader.utils import process_and_finalize_audio
        process_and_finalize_audio(
            downloaded_files=new_files,
            title="Downloaded Track",
            artist="YouTube Downloader",
            cfg=cfg,
        )
        print_banner("AUDIO DOWNLOAD COMPLETE")
        return True
    print(f"\nERROR: Download encountered issues: {stderr[-1000:] if stderr else 'Unknown failure'}")
    return False



