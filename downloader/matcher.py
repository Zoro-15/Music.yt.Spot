import json
from downloader.utils import normalize, words, run_command, get_ytdlp_auth_args

SEARCH_COUNT = 5
MIN_SCORE = 70


def similarity(title, candidate):
    """Calculates word overlap ratio between Spotify title and YouTube candidate title."""
    a = words(title)
    b = words(candidate)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def artist_match(artists, candidate_title, candidate_channel):
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


def bad_candidate(title):
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


def score_candidate(spotify_title, spotify_artists, yt_title, channel):
    """
    Scores a YouTube candidate (0 to 100) based on title similarity, artist presence,
    prefix matching, and penalty words.
    """
    score = 0

    # Title similarity (up to 50 pts)
    title_sim = similarity(spotify_title, yt_title)
    score += min(50, int(title_sim * 50))

    # Artist presence (up to 40 pts)
    score += artist_match(spotify_artists, yt_title, channel)

    # Bad candidate penalty (-35 pts)
    if bad_candidate(yt_title):
        score -= 35

    # Prefix match bonus (+10 pts)
    spotify_norm = normalize(spotify_title)
    youtube_norm = normalize(yt_title)

    if youtube_norm.startswith(spotify_norm):
        score += 10

    return max(0, min(100, score))


def search_youtube(title, artists, count=SEARCH_COUNT, min_score=MIN_SCORE, use_ytmusic=True):
    """
    Queries YouTube using multi-pass search strategy (YTM topic search -> main YT -> fallback query)
    and returns sorted, scored candidates.
    """
    search_queries = []
    if artists:
        search_queries.append(f"{artists} - {title}")
        search_queries.append(f"{artists} {title} Audio")
    search_queries.append(f"{title} Official Audio")
    search_queries.append(f"{title}")

    all_candidates = []
    seen_urls = set()

    for query in search_queries:
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-single-json",
            f"ytsearch{count}:{query}",
        ]

        code, stdout, stderr = run_command(cmd)
        if code != 0:
            continue

        try:
            data = json.loads(stdout)
        except Exception:
            continue

        entries = data.get("entries") or []

        for entry in entries:
            if not entry:
                continue

            yt_title = entry.get("title") or ""
            channel = entry.get("channel") or entry.get("uploader") or ""
            url = entry.get("webpage_url")

            if not url and entry.get("id"):
                url = f"https://www.youtube.com/watch?v={entry['id']}"

            if not yt_title or not url or url in seen_urls:
                continue

            seen_urls.add(url)
            score = score_candidate(title, artists, yt_title, channel)

            all_candidates.append({
                "score": score,
                "title": yt_title,
                "channel": channel,
                "url": url,
            })

        all_candidates.sort(key=lambda x: x["score"], reverse=True)

        # If top candidate meets or exceeds min_score threshold, return immediately
        if all_candidates and all_candidates[0]["score"] >= min_score:
            return all_candidates, ""

    if all_candidates:
        return all_candidates, ""

    return [], "No YouTube search candidates found"

