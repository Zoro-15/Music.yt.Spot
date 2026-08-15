import json
import re
import urllib.parse
import urllib.request
from typing import Optional
from downloader.utils import normalize


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, image/*, */*",
}


def download_image_bytes(url: str, timeout: int = 8) -> Optional[bytes]:
    """Helper to fetch raw image bytes from a URL with validation."""
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


def fetch_itunes_cover_art(title: str, artist: str = "") -> Optional[bytes]:
    """Queries iTunes Search API (Global + Regional IN) for 1400x1400 / 600x600 HD album art."""
    if not title:
        return None

    clean_title = re.sub(r"\(feat\.[^\)]+\)|\[feat\.[^\]]+\]|\(ft\.[^\)]+\)", "", title, flags=re.IGNORECASE).strip()
    clean_title = re.sub(r"\(official[^\)]*\)|\[official[^\]]*\]", "", clean_title, flags=re.IGNORECASE).strip()
    primary_artist = re.split(r",| feat\.| ft\.|&| x ", artist, flags=re.IGNORECASE)[0].strip() if artist else ""

    queries = []
    if clean_title and primary_artist:
        queries.append((f"{clean_title} {primary_artist}", "IN"))
        queries.append((f"{clean_title} {primary_artist}", None))
    if clean_title:
        queries.append((clean_title, "IN"))
        queries.append((clean_title, None))

    title_norm = normalize(clean_title)
    artist_norm = normalize(primary_artist)

    for q, country in queries:
        api_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(q)}&entity=song&limit=5"
        if country:
            api_url += f"&country={country}"

        try:
            req = urllib.request.Request(api_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status != 200:
                    continue
                results = (json.loads(resp.read().decode("utf-8")) or {}).get("results") or []

                for item in results:
                    track_name = normalize(item.get("trackName") or "")
                    item_artist = normalize(item.get("artistName") or "")

                    # Verify title similarity or artist presence
                    if title_norm in track_name or track_name in title_norm or (artist_norm and (artist_norm in item_artist or item_artist in artist_norm)):
                        art_url = item.get("artworkUrl100")
                        if art_url:
                            # Upgrade 100x100 to 1400x1400 / 600x600
                            hd_url = art_url.replace("100x100bb", "1400x1400bb").replace("100x100", "1400x1400")
                            img = download_image_bytes(hd_url) or download_image_bytes(
                                art_url.replace("100x100bb", "600x600bb").replace("100x100", "600x600")
                            )
                            if img:
                                return img
        except Exception:
            continue

    return None


def fetch_deezer_cover_art(title: str, artist: str = "") -> Optional[bytes]:
    """Queries Deezer Public Search API for 1000x1000 HD cover artwork."""
    if not title:
        return None

    clean_title = re.sub(r"\(feat\.[^\)]+\)|\[feat\.[^\]]+\]|\(official[^\)]*\)", "", title, flags=re.IGNORECASE).strip()
    primary_artist = re.split(r",| feat\.| ft\.|&", artist, flags=re.IGNORECASE)[0].strip() if artist else ""
    q = f"{clean_title} {primary_artist}".strip() if primary_artist else clean_title

    api_url = f"https://api.deezer.com/search?q={urllib.parse.quote(q)}&limit=5"
    try:
        req = urllib.request.Request(api_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8")) or {}
                items = data.get("data") or []
                title_norm = normalize(clean_title)
                artist_norm = normalize(primary_artist)

                for track in items:
                    t_title = normalize(track.get("title") or track.get("title_short") or "")
                    t_artist = normalize((track.get("artist") or {}).get("name") or "")
                    album_obj = track.get("album") or {}

                    if title_norm in t_title or t_title in title_norm or (artist_norm and artist_norm in t_artist):
                        for key in ["cover_xl", "cover_big", "cover_medium"]:
                            c_url = album_obj.get(key)
                            if c_url:
                                img = download_image_bytes(c_url)
                                if img:
                                    return img
    except Exception:
        pass
    return None


def fetch_youtube_cover_art(video_url_or_id: Optional[str]) -> Optional[bytes]:
    """Fetches maximum resolution YouTube thumbnail given a URL or video ID."""
    if not video_url_or_id:
        return None
    vid_id = None
    if len(video_url_or_id) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", video_url_or_id):
        vid_id = video_url_or_id
    else:
        m = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", video_url_or_id)
        if m:
            vid_id = m.group(1)

    if not vid_id:
        return None

    for res in ["maxresdefault.jpg", "sddefault.jpg", "hqdefault.jpg"]:
        url = f"https://i.ytimg.com/vi/{vid_id}/{res}"
        img = download_image_bytes(url)
        if img:
            return img
    return None


def fetch_high_res_cover(
    title: str,
    artist: str,
    preferred_url: Optional[str] = None,
    video_url: Optional[str] = None,
) -> Optional[bytes]:
    """
    Multi-Tier HD Cover Art Retriever:
    1. Preferred URL (e.g. Spotify CDN 640x640)
    2. Apple iTunes HD Search API (1400x1400) with global & regional IN store
    3. Deezer HD Search API (1000x1000)
    4. YouTube High-Res Thumbnail (maxresdefault.jpg)
    """
    # Tier 1: Preferred URL (Spotify / Direct)
    if preferred_url:
        img = download_image_bytes(preferred_url)
        if img:
            return img

    # Tier 2: Apple iTunes Search API (HD 1400x1400)
    img = fetch_itunes_cover_art(title, artist)
    if img:
        return img

    # Tier 3: Deezer Search API (HD 1000x1000)
    img = fetch_deezer_cover_art(title, artist)
    if img:
        return img

    # Tier 4: YouTube Thumbnail URL
    if video_url:
        img = fetch_youtube_cover_art(video_url)
        if img:
            return img

    return None


