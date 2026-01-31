"""Tests for Jamendo client."""

from src.music_matching.jamendo_client import JamendoClient


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_search_song_success(monkeypatch):
    client = JamendoClient()
    client.client_id = "test-id"
    client.base_url = "https://example.test"

    payload = {
        "results": [
            {"id": "123", "name": "Hello", "artist_name": "World", "duration": 200},
            {"id": "456", "name": "Hi", "artist_name": "Earth", "duration": 180},
        ]
    }

    def fake_get(url, params=None, timeout=None):  # noqa: ANN001
        return DummyResponse(payload)

    monkeypatch.setattr("requests.get", fake_get)

    results = client.search_song("hello", "world")
    assert len(results) == 2
    assert results[0]["title"] == "Hello"
    assert results[0]["artist"] == "World"
    assert results[0]["jamendo_id"] == "123"


def test_search_song_missing_client(monkeypatch):
    client = JamendoClient()
    client.client_id = ""

    # Ensure requests.get would crash if called, to prove we early-return
    def explode(*args, **kwargs):  # noqa: ANN001, ANN002
        raise AssertionError("requests.get should not be called when client_id missing")

    monkeypatch.setattr("requests.get", explode)

    results = client.search_song("hello")
    assert results == []
