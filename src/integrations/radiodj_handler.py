"""Backward-compatible RadioDJ handler built on the active integration layer."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.database import SessionLocal
from src.database.models import MatchedSong, SongRequest
from src.radiodj_integration.playlist_manager import playlist_manager
from src.radiodj_integration.radiodj_client import radiodj_client

logger = logging.getLogger(__name__)


@dataclass
class RadioDJTrack:
    """Minimal backward-compatible RadioDJ track representation."""

    id: int
    title: str
    artist: str
    album: str = ""
    file_path: str = ""
    duration: int = 0


def _find_track(title: str, artist: str = "") -> Optional[RadioDJTrack]:
    """Find a track in the RadioDJ library using the active client."""
    track_id = radiodj_client.find_track_in_library(artist, title)
    if track_id is None:
        return None
    return RadioDJTrack(id=int(track_id), title=title, artist=artist)


def send_to_radiodj(song_match: Dict[str, Any]) -> Optional[RadioDJTrack]:
    """Queue a matched song in RadioDJ and return a compatible track object."""
    title = song_match.get("title", "")
    artist = song_match.get("artist", "")

    if not title:
        logger.warning("Missing title for RadioDJ lookup")
        return None

    track = _find_track(title, artist or "")
    if not track:
        logger.info("Track not found in RadioDJ: %s by %s", title, artist)
        return None

    queued_track_id = playlist_manager.add_song_to_playlist(
        artist=artist or "",
        title=title,
        use_api=True,
    )
    if queued_track_id is None:
        logger.error("Failed to add to RadioDJ queue: %s", title)
        return None

    logger.info("Added to RadioDJ queue: %s by %s", title, artist)
    return track


def check_radiodj_library(title: str, artist: str = "") -> bool:
    """Check if a song exists in the RadioDJ library."""
    return _find_track(title, artist) is not None


def sync_radiodj_library() -> Dict[str, Any]:
    """Sync matched songs with the RadioDJ library."""
    db = SessionLocal()
    stats = {
        "total_matches": 0,
        "found_in_radiodj": 0,
        "not_found": 0,
        "errors": 0,
    }

    try:
        matches = db.query(MatchedSong).all()
        stats["total_matches"] = len(matches)

        for match in matches:
            try:
                track = _find_track(match.song_title or "", match.artist_name or "")
                if track:
                    stats["found_in_radiodj"] += 1
                    _save_track_mapping(db, match.musicbrainz_id, track)
                else:
                    stats["not_found"] += 1
            except Exception as exc:
                logger.error("Error syncing %s: %s", match.song_title, exc)
                stats["errors"] += 1

        db.commit()
    except Exception as exc:
        logger.error("Sync error: %s", exc)
        stats["errors"] += 1
    finally:
        db.close()

    return stats


def _save_track_mapping(db, musicbrainz_id: str, track: RadioDJTrack):
    """Save a MusicBrainz to RadioDJ track mapping."""
    if not musicbrainz_id:
        return

    try:
        from sqlalchemy import text

        sql = text(
            """
            INSERT INTO radiodj_track_mapping
                (musicbrainz_id, radiodj_track_id, title, artist, file_path)
            VALUES
                (:mb_id, :rdj_id, :title, :artist, :path)
            ON DUPLICATE KEY UPDATE
                radiodj_track_id = :rdj_id,
                title = :title,
                artist = :artist,
                file_path = :path,
                updated_at = CURRENT_TIMESTAMP
            """
        )

        db.execute(
            sql,
            {
                "mb_id": musicbrainz_id,
                "rdj_id": track.id,
                "title": track.title,
                "artist": track.artist,
                "path": track.file_path,
            },
        )
    except Exception as exc:
        logger.error("Failed to save track mapping: %s", exc)


def process_pending_requests() -> Dict[str, Any]:
    """Process all pending requests and queue matches in RadioDJ."""
    db = SessionLocal()
    stats = {
        "processed": 0,
        "queued": 0,
        "not_found": 0,
        "errors": 0,
    }

    try:
        pending = db.query(SongRequest).filter(SongRequest.status == "pending").all()

        for request in pending:
            stats["processed"] += 1
            try:
                match = db.query(MatchedSong).filter(MatchedSong.id == request.matched_song_id).first()
                if not match:
                    continue

                track = send_to_radiodj(
                    {
                        "title": match.song_title or "",
                        "artist": match.artist_name or "",
                    }
                )

                if track:
                    request.status = "queued"
                    request.radiodj_track_id = track.id
                    stats["queued"] += 1
                    logger.info("Queued: %s by %s", match.song_title, match.artist_name)
                else:
                    request.status = "not_found"
                    stats["not_found"] += 1
                    logger.info("Not in library: %s by %s", match.song_title, match.artist_name)
            except Exception as exc:
                logger.error("Error processing request %s: %s", request.id, exc)
                stats["errors"] += 1

        db.commit()
    except Exception as exc:
        logger.error("Process requests error: %s", exc)
    finally:
        db.close()

    return stats


def get_radiodj_status() -> Dict[str, Any]:
    """Get RadioDJ connection status from the active integration layer."""
    try:
        status = radiodj_client.validate_connection()
        now_playing = radiodj_client.get_now_playing()
        queue = radiodj_client.get_queue(limit=5)
        return {
            "connected": status.get("api_available", False)
            or status.get("database_available", False)
            or status.get("filesystem_available", False),
            "api_available": status.get("api_available", False),
            "database_available": status.get("database_available", False),
            "filesystem_available": status.get("filesystem_available", False),
            "now_playing": (
                {
                    "id": now_playing.id,
                    "artist": now_playing.artist,
                    "title": now_playing.title,
                    "album": now_playing.album,
                }
                if now_playing
                else None
            ),
            "queue": [
                {
                    "id": track.id,
                    "artist": track.artist,
                    "title": track.title,
                    "album": track.album,
                }
                for track in queue
            ],
        }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
