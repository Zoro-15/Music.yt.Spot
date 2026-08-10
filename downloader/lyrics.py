import json
import urllib.parse
import urllib.request
from pathlib import Path


def fetch_lyrics(title, artist, album, output_audio_path):
    """
    Queries LRCLIB REST API for synchronized (.lrc) or plain lyrics
    and saves a .lrc file matching the audio file stem.
    Uses standard library urllib (no pip dependencies required).
    """
    if not title or not artist or not output_audio_path:
        return False, "Missing track details"

    base_url = "https://lrclib.net/api/get"
    params = {
        "track_name": title,
        "artist_name": artist,
    }
    if album:
        params["album_name"] = album

    query_str = urllib.parse.urlencode(params)
    request_url = f"{base_url}?{query_str}"

    headers = {
        "User-Agent": "Termux-Playlist-Downloader/1.0 (https://github.com/user/spotify-ytdlp-downloader)"
    }

    try:
        req = urllib.request.Request(request_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                lyrics_text = data.get("syncedLyrics") or data.get("plainLyrics")
                if lyrics_text:
                    lrc_path = Path(output_audio_path).with_suffix(".lrc")
                    with open(lrc_path, "w", encoding="utf-8") as f:
                        f.write(lyrics_text)
                    return True, f"Saved lyrics: {lrc_path.name}"
    except Exception:
        pass

    return False, "No lyrics found"
