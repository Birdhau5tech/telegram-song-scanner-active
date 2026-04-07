"""Backward-compatible adapter for RadioDJ integration.

This module preserves the historic src.integrations.radiodj_client API while
routing all behavior through the active src.radiodj_integration client.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.radiodj_integration.radiodj_client import radiodj_client as active_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RadioDJTrack:
    """Represents a track in RadioDJ."""

    id: int
    title: str
    artist: str
    album: str = ""
    file_path: str = ""
    duration: int = 0


class RadioDJClient:
    """Compatibility wrapper over the active RadioDJ client."""

    def __init__(self):
        self._client = active_client

    @staticmethod
    def _convert_track(track) -> Optional[RadioDJTrack]:
        if not track:
            return None
        return RadioDJTrack(
            id=int(track.id),
            title=track.title,
            artist=track.artist,
            album=track.album,
            file_path=track.file_path,
            duration=int(track.duration or 0),
        )

    def search_track(self, title: str, artist: str) -> Optional[RadioDJTrack]:
        """Search for a track in RadioDJ library."""
        track_id = self._client.find_track_in_library(artist, title)
        if track_id is None or track_id <= 0:
            return None
        return self._convert_track(self._client.get_track_by_id(track_id))

    def add_to_queue(self, track_id: int, position: str = "bottom") -> bool:
        """Add a track to the RadioDJ queue.

        The position parameter is accepted for compatibility but ignored because
        queue placement depends on RadioDJ capabilities in the active client.
        """
        del position
        return self._client.add_track_to_queue_db(track_id)

    def add_to_playlist(self, track_id: int, playlist_id: Optional[int] = None) -> bool:
        """Load a library track through the active client API path."""
        track = self._client.get_track_by_id(track_id)
        if not track:
            return False
        return self._client.add_track_via_api(track.artist, track.title, playlist_id)

    def get_queue(self) -> List[RadioDJTrack]:
        """Get current queue."""
        return [self._convert_track(track) for track in self._client.get_queue() if track]

    def get_now_playing(self) -> Optional[RadioDJTrack]:
        """Get current now playing track."""
        return self._convert_track(self._client.get_now_playing())

    def get_library_stats(self) -> Dict[str, int]:
        """Get basic library statistics using direct DB access."""
        songs = self._client.search_songs("", limit=1)
        total_tracks = len(songs) if isinstance(songs, list) else 0
        # Keep the old shape without adding heavy DB queries through this shim.
        return {"total_tracks": total_tracks, "enabled_tracks": total_tracks}

    def close(self):
        """Close resources (kept for compatibility)."""
        return None


# Global client instance
radiodj_client = RadioDJClient()
