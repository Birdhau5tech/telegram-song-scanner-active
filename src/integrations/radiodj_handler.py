"""Handle sending matched songs to RadioDJ."""

import logging
from typing import Optional, Dict, Any, List
from config.database import SessionLocal
from src.database.models import MatchedSong, SongRequest
from .radiodj_client import radiodj_client, RadioDJTrack

logger = logging.getLogger(__name__)


def send_to_radiodj(song_match: Dict[str, Any]) -> Optional[RadioDJTrack]:
    """
    Send a matched song to RadioDJ queue.
    
    Args:
        song_match: Dict with 'title', 'artist', 'album', etc.
        
    Returns:
        RadioDJTrack if found and queued, None otherwise
    """
    title = song_match.get("title", "")
    artist = song_match.get("artist", "")
    
    if not title:
        logger.warning("Missing title for RadioDJ lookup")
        return None
    
    # Search RadioDJ library
    track = radiodj_client.search_track(title, artist or "")
    
    if not track:
        logger.info(f"Track not found in RadioDJ: {title} by {artist}")
        return None
    
    # Add to queue
    if radiodj_client.add_to_queue(track.id):
        logger.info(f"✅ Added to RadioDJ queue: {track.title} by {track.artist}")
        return track
    
    logger.error(f"Failed to add to RadioDJ queue: {track.title}")
    return None


def check_radiodj_library(title: str, artist: str = "") -> bool:
    """Check if a song exists in RadioDJ library."""
    track = radiodj_client.search_track(title, artist)
    return track is not None


def sync_radiodj_library() -> Dict[str, Any]:
    """
    Sync matched songs with RadioDJ library.
    Updates the radiodj_track_mapping table.
    
    Returns:
        Dict with sync statistics
    """
    db = SessionLocal()
    stats = {
        "total_matches": 0,
        "found_in_radiodj": 0,
        "not_found": 0,
        "errors": 0
    }
    
    try:
        # Get all matched songs
        matches = db.query(MatchedSong).all()
        stats["total_matches"] = len(matches)
        
        for match in matches:
            try:
                track = radiodj_client.search_track(
                    match.song_title or "",
                    match.artist_name or ""
                )
                
                if track:
                    stats["found_in_radiodj"] += 1
                    # Store mapping in database
                    _save_track_mapping(db, match.musicbrainz_id, track)
                else:
                    stats["not_found"] += 1
                    
            except Exception as e:
                logger.error(f"Error syncing {match.song_title}: {e}")
                stats["errors"] += 1
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Sync error: {e}")
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
        
        # Upsert the mapping
        sql = text("""
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
        """)
        
        db.execute(sql, {
            "mb_id": musicbrainz_id,
            "rdj_id": track.id,
            "title": track.title,
            "artist": track.artist,
            "path": track.file_path
        })
        
    except Exception as e:
        logger.error(f"Failed to save track mapping: {e}")


def process_pending_requests() -> Dict[str, Any]:
    """
    Process all pending song requests and add them to RadioDJ queue.
    
    Returns:
        Dict with processing statistics
    """
    db = SessionLocal()
    stats = {
        "processed": 0,
        "queued": 0,
        "not_found": 0,
        "errors": 0
    }
    
    try:
        # Get pending requests with their matched songs
        pending = db.query(SongRequest).filter(
            SongRequest.status == "pending"
        ).all()
        
        for request in pending:
            stats["processed"] += 1
            
            try:
                # Get the matched song
                match = db.query(MatchedSong).filter(
                    MatchedSong.id == request.matched_song_id
                ).first()
                
                if not match:
                    continue
                
                # Try to find and queue in RadioDJ
                track = radiodj_client.search_track(
                    match.song_title or "",
                    match.artist_name or ""
                )
                
                if track:
                    if radiodj_client.add_to_queue(track.id):
                        request.status = "queued"
                        request.radiodj_track_id = track.id
                        stats["queued"] += 1
                        logger.info(f"Queued: {match.song_title} by {match.artist_name}")
                    else:
                        stats["errors"] += 1
                else:
                    request.status = "not_found"
                    stats["not_found"] += 1
                    logger.info(f"Not in library: {match.song_title} by {match.artist_name}")
                
            except Exception as e:
                logger.error(f"Error processing request {request.id}: {e}")
                stats["errors"] += 1
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Process requests error: {e}")
    finally:
        db.close()
    
    return stats


def get_radiodj_status() -> Dict[str, Any]:
    """Get RadioDJ connection status and stats."""
    try:
        stats = radiodj_client.get_library_stats()
        queue = radiodj_client.get_queue()
        now_playing = radiodj_client.get_now_playing()
        
        return {
            "connected": stats.get("total_tracks", 0) > 0,
            "library": stats,
            "queue_length": len(queue),
            "now_playing": {
                "title": now_playing.title if now_playing else None,
                "artist": now_playing.artist if now_playing else None
            } if now_playing else None
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }
