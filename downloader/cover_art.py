import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional
from downloader.utils import normalize, words
from downloader.matcher import similarity


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


def is_valid_cover_match(
    target_title: str,
    target_artist: str,
    candidate_title: str,
    candidate_artist: str,
    min_title_similarity: float = 0.65,
) -> bool:
    """
    Validates whether an online metadata result (from iTunes or Deezer) is a true match for the target song.
    Requires BOTH a high title similarity AND an artist match (if target artist is specified).
    Prevents false matches where popular songs by the same artist are mistakenly selected.
    """
    if not target_title or not candidate_title:
        return False

    clean_t = re.sub(r"\(feat\.[^\)]+\)|\[feat\.[^\]]+\]|\(official[^\)]*\)", "", target_title, flags=re.IGNORECASE).strip()
    clean_c = re.sub(r"\(feat\.[^\)]+\)|\[feat\.[^\]]+\]|\(official[^\)]*\)", "", candidate_title, flags=re.IGNORECASE).strip()

    t_norm = normalize(clean_t)
    c_norm = normalize(clean_c)

    if not t_norm or not c_norm:
        return False

    # Check fuzzy title similarity
    sim = similarity(clean_t, clean_c)
    title_matches = sim >= min_title_similarity or t_norm == c_norm

    # Check for exact substring if both titles have sufficient length (> 4 chars)
    if not title_matches and len(t_norm) > 4 and len(c_norm) > 4:
        if t_norm in c_norm or c_norm in t_norm:
            w_t = words(t_norm)
            w_c = words(c_norm)
            if w_t and w_c and (len(w_t & w_c) / max(len(w_t), 1)) >= 0.7:
                title_matches = True

    if not title_matches:
        return False

    # If target artist is not specified, require high title similarity
    if not target_artist or not target_artist.strip():
        return sim >= 0.85 or t_norm == c_norm

    # If target artist is specified, candidate artist MUST match
    a_cand_norm = normalize(candidate_artist)
    if not a_cand_norm:
        return False

    artists_list = [a.strip() for a in re.split(r",| feat\.| ft\.|&| x ", target_artist, flags=re.IGNORECASE) if a.strip()]
    artist_matches = False
    for a in artists_list:
        a_norm = normalize(a)
        if not a_norm:
            continue
        if a_norm in a_cand_norm or a_cand_norm in a_norm:
            artist_matches = True
            break
        w_a = words(a_norm)
        w_cand = words(a_cand_norm)
        if w_a and w_cand and len(w_a & w_cand) >= max(1, len(w_a) // 2):
            artist_matches = True
            break

    return artist_matches


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
                    track_name = item.get("trackName") or ""
                    item_artist = item.get("artistName") or ""

                    # Verify title similarity and artist presence strictly
                    if is_valid_cover_match(clean_title, primary_artist or artist, track_name, item_artist):
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

                for track in items:
                    t_title = track.get("title") or track.get("title_short") or ""
                    t_artist = (track.get("artist") or {}).get("name") or ""
                    album_obj = track.get("album") or {}

                    if is_valid_cover_match(clean_title, primary_artist or artist, t_title, t_artist):
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
    """Fetches maximum resolution YouTube thumbnail given a URL or video ID and crops to square."""
    if not video_url_or_id:
        return None
    vid_id = None
    if len(video_url_or_id) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", video_url_or_id):
        vid_id = video_url_or_id
    else:
        m = re.search(r"(?:v=|\/|youtu\.be\/|embed\/)([a-zA-Z0-9_-]{11})", video_url_or_id)
        if m:
            vid_id = m.group(1)

    if not vid_id:
        return None

    for res in ["maxresdefault.jpg", "sddefault.jpg", "hqdefault.jpg", "0.jpg", "hq720.jpg"]:
        url = f"https://i.ytimg.com/vi/{vid_id}/{res}"
        img = download_image_bytes(url)
        if img:
            return crop_image_bytes_to_square(img)
    return None


def crop_image_bytes_to_square(image_bytes: bytes) -> bytes:
    """Crops raw image bytes to a 1:1 square aspect ratio using FFmpeg in an isolated temp directory."""
    if not image_bytes or len(image_bytes) < 1000:
        return image_bytes
    try:
        import uuid
        import tempfile
        from downloader.utils import run_command
        temp_dir = Path(tempfile.gettempdir()) / "music_yt_spot_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        in_tmp = temp_dir / f"crop_in_{uuid.uuid4().hex}.jpg"
        out_tmp = temp_dir / f"crop_out_{uuid.uuid4().hex}.jpg"
        in_tmp.write_bytes(image_bytes)
        code, _, _ = run_command(["ffmpeg", "-y", "-i", str(in_tmp), "-vf", "crop='min(iw,ih):min(iw,ih)'", str(out_tmp)])
        if code == 0 and out_tmp.exists() and out_tmp.stat().st_size > 500:
            result = out_tmp.read_bytes()
            if in_tmp.exists():
                in_tmp.unlink()
            if out_tmp.exists():
                out_tmp.unlink()
            return result
        if in_tmp.exists():
            in_tmp.unlink()
        if out_tmp.exists():
            out_tmp.unlink()
    except Exception:
        pass
    return image_bytes


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
    3. Deezer API (1000x1000)
    4. YouTube Maximum Resolution Thumbnail (maxresdefault.jpg, cropped to square)
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

    # Tier 4: YouTube High-Res Thumbnail
    if video_url:
        img = fetch_youtube_cover_art(video_url)
        if img:
            return img

    return None
