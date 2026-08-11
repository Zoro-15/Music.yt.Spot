import json
import re
import urllib.parse
import urllib.request
from typing import Optional


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def download_image_bytes(url: str, timeout: int = 8) -> Optional[bytes]:
    """Helper to fetch raw image bytes from a URL."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read()
                return data if len(data) > 1000 else None
    except Exception:
        pass
    return None


def fetch_itunes_cover_art(title: str, artist: str) -> Optional[bytes]:
    """Queries iTunes Search API for 600x600 / 1400x1400 HD album art."""
    if not title:
        return None
    clean_title = re.sub(r"\(feat\.[^\)]+\)", "", title, flags=re.IGNORECASE).strip()
    primary_artist = re.split(r",| feat\.| ft\.|&", artist, flags=re.IGNORECASE)[0].strip() if artist else ""
    query = f"{clean_title} {primary_artist}".strip()
    api_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"

    try:
        req = urllib.request.Request(api_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                results = (json.loads(resp.read().decode("utf-8")) or {}).get("results") or []
                if results and results[0].get("artworkUrl100"):
                    art_url = results[0]["artworkUrl100"]
                    hd_url = art_url.replace("100x100bb", "1400x1400bb").replace("100x100", "1400x1400")
                    return download_image_bytes(hd_url) or download_image_bytes(art_url.replace("100x100bb", "600x600bb").replace("100x100", "600x600"))
    except Exception:
        pass
    return None


def fetch_high_res_cover(title: str, artist: str, preferred_url: Optional[str] = None) -> Optional[bytes]:
    """Main cover art retriever: downloads preferred_url or falls back to iTunes Search API."""
    return download_image_bytes(preferred_url) if preferred_url else fetch_itunes_cover_art(title, artist)

