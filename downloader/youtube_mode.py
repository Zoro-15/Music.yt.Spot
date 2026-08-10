from downloader.config import load_config
from downloader.ffmpeg_tagger import crop_square_artwork
from downloader.utils import (
    OUTPUT_DIR,
    DATA_DIR,
    run_command,
    print_banner,
    sync_to_android_music,
)


def download_from_link(url):
    """
    Universal link downloader. Handles:
    - YouTube Music playlists & albums (music.youtube.com/playlist?list=...)
    - Standard YouTube playlists (youtube.com/playlist?list=...)
    - YouTube Music single tracks (music.youtube.com/watch?v=...)
    - Standard YouTube videos & music videos (youtube.com/watch?v=...)
    """
    if not url or not url.strip():
        print("ERROR: Please provide a valid URL.")
        return False

    url = url.strip()
    is_playlist = "list=" in url or "/playlist" in url or "/album" in url

    if is_playlist:
        return download_youtube_playlist(url)
    else:
        return download_youtube_video(url)


def download_youtube_playlist(url):
    """
    Downloads a complete YouTube or YT Music playlist/album directly using yt-dlp
    with native audio preservation, archive tracking, thumbnail embedding, and index ordering.
    """
    cfg = load_config()
    print_banner("Playlist / Album Downloader Mode")
    print(f" Target URL       : {url}")
    print(f" Output Directory : {OUTPUT_DIR}\n")

    archive_file = DATA_DIR / "downloaded_archive.txt"
    output_template = str(OUTPUT_DIR / "%(playlist_index)03d - %(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--yes-playlist",
        "--download-archive", str(archive_file),
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
        url,
    ]

    print("Executing yt-dlp playlist/album download...")
    code, stdout, stderr = run_command(cmd)

    if code == 0:
        # Crop downloaded artwork & sync to Android Music
        for img in OUTPUT_DIR.glob("*.*"):
            if img.suffix.lower() in [".webp", ".jpg", ".jpeg"] and cfg.get("square_crop_artwork", True):
                crop_square_artwork(img)
        for audio in OUTPUT_DIR.glob("*.*"):
            if audio.suffix.lower() in [".m4a", ".webm", ".opus", ".mp3", ".aac"] and cfg.get("auto_sync_android_music", True):
                sync_to_android_music(audio)

        print_banner("PLAYLIST / ALBUM DOWNLOAD COMPLETE")
        return True
    else:
        print("\nERROR: Download encountered issues:")
        print(stderr[-2000:] if stderr else "Unknown download failure")
        return False


def download_youtube_video(url):
    """
    Downloads a single YouTube or YT Music video audio file natively with metadata and thumbnail.
    """
    cfg = load_config()
    print_banner("Single Audio / Music Video Downloader Mode")
    print(f" Target URL       : {url}")
    print(f" Output Directory : {OUTPUT_DIR}\n")

    output_template = str(OUTPUT_DIR / "%(title)s.%(ext)s")

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
        url,
    ]

    print("Executing yt-dlp download...")
    code, stdout, stderr = run_command(cmd)

    if code == 0:
        for img in OUTPUT_DIR.glob("*.*"):
            if img.suffix.lower() in [".webp", ".jpg", ".jpeg"] and cfg.get("square_crop_artwork", True):
                crop_square_artwork(img)
        for audio in OUTPUT_DIR.glob("*.*"):
            if audio.suffix.lower() in [".m4a", ".webm", ".opus", ".mp3", ".aac"] and cfg.get("auto_sync_android_music", True):
                sync_to_android_music(audio)

        print_banner("AUDIO DOWNLOAD COMPLETE")
        return True
    else:
        print("\nERROR: Download encountered issues:")
        print(stderr[-2000:] if stderr else "Unknown download failure")
        return False
