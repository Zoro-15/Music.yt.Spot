import json
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Set, Any, Optional
from downloader.utils import normalize, words, run_command

SEARCH_COUNT = 5
MIN_SCORE = 70


def similarity(title: str, candidate: str) -> float:
    """
    Calculates combined title similarity using fuzzy sequence matching (difflib)
    and set word overlap.
    """
    a_norm = normalize(title)
    b_norm = normalize(candidate)

    if not a_norm or not b_norm:
        return 0.0

    # 1. Fuzzy Sequence Ratio (handles word order, minor spelling differences)
    seq_ratio = SequenceMatcher(None, a_norm, b_norm).ratio()

    # 2. Word Set Overlap Ratio
    w_a = words(title)
    w_b = words(candidate)
    set_ratio = (len(w_a & w_b) / len(w_a)) if w_a else 0.0

    # Weighted average: 60% sequence ratio, 40% set overlap
    return (0.6 * seq_ratio) + (0.4 * set_ratio)


def artist_match(artists: str, candidate_title: str, candidate_channel: str) -> int:
    """Evaluates artist presence in candidate title or channel name."""
    haystack = normalize(f"{candidate_title} {candidate_channel}")
    score = 0

    if not artists:
        return 0

    artist_list = [a.strip() for a in artists.split(",") if a.strip()]

    for artist in artist_list:
        artist_norm = normalize(artist)
        if not artist_norm:
            continue

        if artist_norm in haystack:
            score += 30
        else:
            artist_w = words(artist)
            if artist_w:
                overlap = len(artist_w & words(haystack))
                if overlap >= max(1, len(artist_w) // 2):
                    score += 15

    return min(score, 40)


def bad_candidate(title: str) -> bool:
    """Detects unwanted track variants (slowed, reverb, cover, remix, etc.)."""
    t = normalize(title)
    bad_words = [
        "slowed",
        "reverb",
        "sped up",
        "speed up",
        "8d",
        "nightcore",
        "remix",
        "cover",
        "reaction",
        "karaoke",
        "instrumental",
        "live",
        "shorts",
    ]
    return any(w in t for w in bad_words)


def score_candidate(
    spotify_title: str,
    spotify_artists: str,
    yt_title: str,
    channel: str,
    candidate_duration: Optional[int] = None,
    target_duration: Optional[int] = None,
) -> int:
    """Scores a YouTube candidate (0 to 100) based on title, artist, topic channel, duration, and penalties."""
    score = 0
    score += min(50, int(similarity(spotify_title, yt_title) * 50))
    score += artist_match(spotify_artists, yt_title, channel)

    if bad_candidate(yt_title):
        score -= 35

    # Phase 2 Feature: Official Topic Channel Bonus (+20 pts)
    chan_norm = normalize(channel)
    if "topic" in chan_norm or channel.endswith("- Topic"):
        score += 20

    if candidate_duration and target_duration and candidate_duration > 0 and target_duration > 0:
        diff = abs(candidate_duration - target_duration)
        if diff <= 5:
            score += 15
        elif diff <= 10:
            score += 5
        elif diff > 30:
            score -= 40
        elif diff > 15:
            score -= 20

    if normalize(yt_title).startswith(normalize(spotify_title)):
        score += 10

    return max(0, min(100, score))


def search_youtube(
    title: str,
    artists: str,
    count: int = SEARCH_COUNT,
    min_score: int = MIN_SCORE,
    use_ytmusic: bool = True,
    target_duration_sec: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Queries YouTube using fast 1-pass search strategy to minimize subprocess overhead."""
    primary_query = f"{artists} - {title} Topic" if artists else f"{title} Official Audio"
    fallback_query = f"{artists} {title}" if artists else title

    all_candidates: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()

    for query in [primary_query, fallback_query]:
        cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", f"ytsearch{count}:{query}"]
        code, stdout, _ = run_command(cmd)
        if code != 0 or not stdout.strip():
            continue

        try:
            entries = (json.loads(stdout) or {}).get("entries") or []
        except Exception:
            continue

        for entry in entries:
            if not entry:
                continue
            yt_title = entry.get("title") or ""
            channel = entry.get("channel") or entry.get("uploader") or ""
            url = entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={entry['id']}" if entry.get("id") else None)
            candidate_duration = entry.get("duration")

            if not yt_title or not url or url in seen_urls:
                continue

            seen_urls.add(url)
            cand_score = score_candidate(title, artists, yt_title, channel, candidate_duration, target_duration_sec)
            all_candidates.append({
                "score": cand_score,
                "title": yt_title,
                "channel": channel,
                "url": url,
                "duration": candidate_duration,
            })

        all_candidates.sort(key=lambda x: x["score"], reverse=True)
        if all_candidates and all_candidates[0]["score"] >= min_score:
            return all_candidates, ""

    return (all_candidates, "") if all_candidates else ([], "No YouTube candidates found")

