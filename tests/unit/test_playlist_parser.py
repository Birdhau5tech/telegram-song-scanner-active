"""Unit tests for playlist parser URL detection."""
from src.playlist_parser import playlist_parser


def test_detect_spotify_playlist_url():
    text = "Check this out: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    info = playlist_parser.detect_playlist_url(text)
    assert info is not None
    assert info["platform"] == "spotify"
    assert info["playlist_id"]


def test_detect_spotify_album_url():
    text = "Album link: https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy"
    info = playlist_parser.detect_playlist_url(text)
    assert info is not None
    assert info["platform"] == "spotify_album"
    assert info["playlist_id"]


def test_detect_youtube_playlist_url():
    text = "YT playlist: https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI"
    info = playlist_parser.detect_playlist_url(text)
    assert info is not None
    assert info["platform"] == "youtube"


def test_no_playlist_url():
    text = "No playlist here, just text."
    info = playlist_parser.detect_playlist_url(text)
    assert info is None
