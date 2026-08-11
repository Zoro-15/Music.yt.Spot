import pytest
from downloader.matcher import similarity, artist_match, bad_candidate, score_candidate


def test_similarity():
    assert similarity("Blinding Lights", "Blinding Lights") == 1.0
    assert similarity("Starboy", "Starboy (Official Music Video)") > 0.6
    assert similarity("Song A", "Completely Different B") < 0.3


def test_artist_match():
    assert artist_match("The Weeknd", "Starboy", "The Weeknd - Topic") >= 30
    assert artist_match("Post Malone, Swae Lee", "Sunflower (Spider-Man)", "PostMaloneVEVO") >= 15
    assert artist_match("Unknown Artist", "Random Song", "Random Channel") == 0


def test_bad_candidate():
    assert bad_candidate("Song Name (Slowed + Reverb)") is True
    assert bad_candidate("Song Name (Speed Up)") is True
    assert bad_candidate("Song Name 8D Audio") is True
    assert bad_candidate("Official Music Video") is False


def test_score_candidate():
    # Official topic channel match with good title & duration
    score = score_candidate(
        spotify_title="Blinding Lights",
        spotify_artists="The Weeknd",
        yt_title="Blinding Lights",
        channel="The Weeknd - Topic",
        candidate_duration=200,
        target_duration=202,
    )
    assert score >= 85

    # Bad candidate penalty (slowed)
    slowed_score = score_candidate(
        spotify_title="Blinding Lights",
        spotify_artists="The Weeknd",
        yt_title="Blinding Lights (Slowed + Reverb)",
        channel="Random uploader",
        candidate_duration=250,
        target_duration=202,
    )
    assert slowed_score < score
