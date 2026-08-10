from downloader.utils import run_command


def apply_spotify_metadata(audio_file, title, artist, album):
    """
    Injects track title, artist, album, genre, and source comment into the audio file
    using FFmpeg stream copy (-c copy). Does NOT re-encode audio.
    """
    if not audio_file.exists():
        return False, "Audio file does not exist"

    temp_file = audio_file.with_name(f"{audio_file.stem}.metadata{audio_file.suffix}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_file),
        "-map",
        "0",
        "-c",
        "copy",
        "-metadata",
        f"title={title}",
        "-metadata",
        f"artist={artist}",
        "-metadata",
        f"album={album}",
        "-metadata",
        "genre=Music",
        "-metadata",
        "comment=Spotify playlist source",
        str(temp_file),
    ]

    code, _, stderr = run_command(cmd)

    if code == 0 and temp_file.exists():
        try:
            temp_file.replace(audio_file)
            return True, "Metadata written successfully"
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            return False, f"Failed to replace audio file: {e}"
def crop_square_artwork(image_path):
    """
    Crops downloaded artwork (.webp / .jpg) to a 1:1 square aspect ratio using FFmpeg.
    Eliminates letterboxing (black top/bottom or side bars).
    """
    if not image_path or not image_path.exists():
        return False, "Image file not found"

    temp_crop = image_path.with_name(f"{image_path.stem}.crop{image_path.suffix}")

    # FFmpeg crop filter: crop='min(iw,ih):min(iw,ih)'
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(image_path),
        "-vf", "crop='min(iw,ih):min(iw,ih)'",
        str(temp_crop),
    ]

    code, _, _ = run_command(cmd)
    if code == 0 and temp_crop.exists():
        try:
            temp_crop.replace(image_path)
            return True, "Square crop successful"
        except Exception as e:
            if temp_crop.exists():
                temp_crop.unlink()
            return False, f"Replace failed: {e}"
    else:
        if temp_crop.exists():
            temp_crop.unlink()
        return False, "FFmpeg crop failed"

