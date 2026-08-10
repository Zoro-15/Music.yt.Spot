from downloader.config import load_config
from downloader.ffmpeg_tagger import apply_spotify_metadata, crop_square_artwork
from downloader.lyrics import fetch_lyrics
from downloader.matcher import search_youtube
from downloader.utils import (
    OUTPUT_DIR,
    run_command,
    sanitize_filename,
    print_banner,
    sync_to_android_music,
)


def search_and_download_song(query):
    """
    Searches YouTube / YouTube Music by song name, displays top candidate,
    and downloads native audio, artwork (cropped 1:1), metadata, and synced lyrics.
    """
    if not query or not query.strip():
        print("ERROR: Please provide a song name or search query.")
        return False

    query = query.strip()
    print_banner(f"Searching Song: '{query}'")

    cfg = load_config()
    min_score = cfg.get("min_score", 50)
    use_ytmusic = cfg.get("ytmusic_priority", True)

    candidates, error = search_youtube(
        title=query, artists="", min_score=min_score, use_ytmusic=use_ytmusic
    )

    if error or not candidates:
        print(f"✖ Search failed: {error or 'No candidates found'}")
        return False

    print("Top Search Candidates:")
    for idx, c in enumerate(candidates[:3], 1):
        print(f"  [{idx}] {c['title']} | Channel: {c['channel']} (Score: {c['score']})")

    best = candidates[0]
    print("\nSelected Best Match:")
    print(f"  Title  : {best['title']}")
    print(f"  Channel: {best['channel']}")
    print(f"  URL    : {best['url']}\n")

    safe_title = sanitize_filename(best["title"])
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

    print("Downloading audio stream...")
    code, stdout, stderr = run_command(cmd)

    if code != 0:
        print("✖ Download failed")
        print(stderr[-1500:] if stderr else "Unknown error")
        return False

    # Find downloaded files
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

        # 1. Apply basic metadata if channel/title are present
        apply_spotify_metadata(audio, best["title"], best["channel"], "Single Search")

        # 2. Crop 1:1 square artwork if enabled
        if thumb_files and cfg.get("square_crop_artwork", True):
            crop_square_artwork(thumb_files[0])

        # 3. Fetch LRCLIB lyrics if enabled
        if cfg.get("fetch_lyrics", True):
            fetch_lyrics(best["title"], best["channel"], "", audio)

        # 4. Sync to Android Music folder if enabled
        if cfg.get("auto_sync_android_music", True):
            sync_to_android_music(audio)

    print_banner(f"✓ SONG DOWNLOAD COMPLETE: {best['title']}")
    return True
