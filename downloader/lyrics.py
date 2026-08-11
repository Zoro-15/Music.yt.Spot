import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Tuple, Union, Optional


def clean_artist_name(artist: str) -> str:
    """Strips feat/ft/collaborators to get primary artist for LRCLIB search."""
    if not artist:
        return ""
    # Extract primary artist before comma, feat, or ft
    primary = re.split(r",| feat\.| ft\.|&", artist, flags=re.IGNORECASE)[0]
    return primary.strip()


def fetch_lyrics(title: str, artist: str, album: str, output_audio_path: Path) -> Tuple[bool, Union[Path, str]]:
    """
    Queries LRCLIB REST API for synchronized (.lrc) or plain lyrics using multi-pass search
    (exact match -> primary artist match -> fuzzy title search).
    Saves a .lrc file matching the audio file stem.
    """
    if not title or not output_audio_path:
        return False, "Missing track details"

    headers = {
        "User-Agent": "MusicYtSpot-Termux/2.0 (https://github.com/Zoro-15/Music.yt.Spot)"
    }

    primary_artist = clean_artist_name(artist)
    clean_title = re.sub(r"\(feat\.[^\)]+\)", "", title, flags=re.IGNORECASE).strip()

    # Pass 1: Direct /api/get query
    get_url = f"https://lrclib.net/api/get?track_name={urllib.parse.quote(clean_title)}&artist_name={urllib.parse.quote(primary_artist)}"
    try:
        req = urllib.request.Request(get_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                lyrics = data.get("syncedLyrics") or data.get("plainLyrics")
                if lyrics:
                    return _save_lrc(output_audio_path, lyrics)
    except Exception:
        pass

    # Pass 2: Fuzzy /api/search query
    search_url = f"https://lrclib.net/api/search?q={urllib.parse.quote(f'{clean_title} {primary_artist}')}"
    try:
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                results = json.loads(resp.read().decode("utf-8"))
                if isinstance(results, list):
                    for item in results:
                        lyrics = item.get("syncedLyrics") or item.get("plainLyrics")
                        if lyrics:
                            return _save_lrc(output_audio_path, lyrics)
    except Exception:
        pass

    return False, "No lyrics found on LRCLIB"


def _save_lrc(output_audio_path: Path, lyrics_text: str) -> Tuple[bool, Path]:
    """Helper to write lyrics to .lrc file next to audio track."""
    lrc_path = Path(output_audio_path).with_suffix(".lrc")
    with open(lrc_path, "w", encoding="utf-8") as f:
        f.write(lyrics_text)
    return True, lrc_path

