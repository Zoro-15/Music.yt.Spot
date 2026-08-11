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
    cfg = load_config()
    print_banner("Playlist / Album Downloader Mode")
    archive_file = DATA_DIR / "downloaded_archive.txt"
    output_template = str(OUTPUT_DIR / "%(playlist_index)03d - %(title)s.%(ext)s")
    before_files = set(OUTPUT_DIR.glob("*.*"))

    cmd = ["yt-dlp", "--yes-playlist", "--download-archive", str(archive_file), "--retries", "5", "--fragment-retries", "5", "--retry-sleep", "2", "--socket-timeout", "30", "--continue"] + get_audio_quality_args(cfg) + ["--add-metadata", "--embed-thumbnail", "--write-thumbnail"] + get_ytdlp_auth_args() + ["-o", output_template, url]
    code, stdout, stderr = run_command(cmd)

    if code == 0:
        new_files = set(OUTPUT_DIR.glob("*.*")) - before_files
        audio_files = []
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
                audio_files.append(target_f)
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

    cmd = ["yt-dlp", "--no-playlist", "--retries", "5", "--fragment-retries", "5", "--retry-sleep", "2", "--socket-timeout", "30", "--continue"] + get_audio_quality_args(cfg) + ["--add-metadata", "--embed-thumbnail", "--write-thumbnail"] + get_ytdlp_auth_args() + ["-o", output_template, url]
    code, stdout, stderr = run_command(cmd)

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
        print_banner("AUDIO DOWNLOAD COMPLETE")
        return True
    print(f"\nERROR: Download encountered issues: {stderr[-1000:] if stderr else 'Unknown failure'}")
    return False


