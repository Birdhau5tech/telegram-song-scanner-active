"""RadioDJ API client for playlist management."""

import os
import logging
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RadioDJTrack:
    """Represents a track in RadioDJ."""
    id: int
    title: str
    artist: str
    album: str
    file_path: str
    duration: int


class RadioDJClient:
    """Client for RadioDJ API integration.
    
    RadioDJ can be accessed via:
    1. Direct MySQL/MariaDB connection (RadioDJ uses MySQL)
    2. HTTP API (if RadioDJ API plugin is installed)
    3. File-based queue (RadioDJ monitors a folder)
    
    This client supports all three methods.
    """
    
    def __init__(self):
        self.api_url = os.getenv("RADIODJ_API_URL", "http://localhost:7000")
        self.api_key = os.getenv("RADIODJ_API_KEY", "")
        self.default_playlist_id = int(os.getenv("RADIODJ_DEFAULT_PLAYLIST_ID", "1"))
        self.auto_queue = os.getenv("RADIODJ_AUTO_QUEUE", "true").lower() == "true"
        
        # RadioDJ database settings (if using direct DB connection)
        self.db_host = os.getenv("RADIODJ_DB_HOST", "localhost")
        self.db_port = int(os.getenv("RADIODJ_DB_PORT", "3306"))
        self.db_name = os.getenv("RADIODJ_DB_NAME", "radiodj")
        self.db_user = os.getenv("RADIODJ_DB_USER", "root")
        self.db_pass = os.getenv("RADIODJ_DB_PASS", "")
        
        self._db_connection = None
        
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make an API request to RadioDJ."""
        url = f"{self.api_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        
        try:
            response = requests.request(method, url, headers=headers, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"RadioDJ API error: {e}")
            return None
    
    def _get_db_connection(self):
        """Get a connection to the RadioDJ database."""
        if self._db_connection is None:
            try:
                import pymysql
                self._db_connection = pymysql.connect(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_pass,
                    database=self.db_name,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
            except Exception as e:
                logger.error(f"Failed to connect to RadioDJ database: {e}")
                return None
        return self._db_connection
    
    def search_track(self, title: str, artist: str) -> Optional[RadioDJTrack]:
        """Search for a track in RadioDJ library."""
        # Try API first
        result = self._request("GET", "tracks/search", params={
            "title": title,
            "artist": artist
        })
        
        if result and result.get("tracks"):
            track = result["tracks"][0]
            return RadioDJTrack(
                id=track["id"],
                title=track["title"],
                artist=track["artist"],
                album=track.get("album", ""),
                file_path=track["path"],
                duration=track.get("duration", 0)
            )
        
        # Fallback to direct database query
        return self._search_track_db(title, artist)
    
    def _search_track_db(self, title: str, artist: str) -> Optional[RadioDJTrack]:
        """Search RadioDJ database directly."""
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cursor:
                # RadioDJ stores tracks in the 'songs' table
                sql = """
                    SELECT ID, title, artist, album, path, duration
                    FROM songs
                    WHERE (title LIKE %s OR title LIKE %s)
                    AND (artist LIKE %s OR artist LIKE %s)
                    AND enabled = 1
                    LIMIT 1
                """
                title_pattern = f"%{title}%"
                artist_pattern = f"%{artist}%"
                cursor.execute(sql, (title_pattern, title, artist_pattern, artist))
                row = cursor.fetchone()
                
                if row:
                    return RadioDJTrack(
                        id=row['ID'],
                        title=row['title'],
                        artist=row['artist'],
                        album=row.get('album', ''),
                        file_path=row['path'],
                        duration=row.get('duration', 0)
                    )
        except Exception as e:
            logger.error(f"RadioDJ DB search error: {e}")
            self._db_connection = None  # Reset connection on error
        
        return None
    
    def add_to_queue(self, track_id: int, position: str = "bottom") -> bool:
        """Add a track to the RadioDJ queue."""
        # Try API
        result = self._request("POST", "queue/add", json={
            "track_id": track_id,
            "position": position
        })
        
        if result is not None:
            return result.get("success", False)
        
        # Fallback to database
        return self._add_to_queue_db(track_id)
    
    def _add_to_queue_db(self, track_id: int) -> bool:
        """Add to queue via RadioDJ database."""
        conn = self._get_db_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cursor:
                # RadioDJ uses 'queuelist' table for the queue
                sql = """
                    INSERT INTO queuelist (songID, requestID, tracktype, artist, title)
                    SELECT ID, 0, song_type, artist, title FROM songs WHERE ID = %s
                """
                cursor.execute(sql, (track_id,))
                conn.commit()
                logger.info(f"Added track {track_id} to RadioDJ queue via database")
                return True
        except Exception as e:
            logger.error(f"Failed to add to RadioDJ queue: {e}")
            self._db_connection = None
        
        return False
    
    def add_to_playlist(self, track_id: int, playlist_id: Optional[int] = None) -> bool:
        """Add a track to a RadioDJ playlist."""
        playlist_id = playlist_id or self.default_playlist_id
        result = self._request("POST", f"playlists/{playlist_id}/tracks", json={
            "track_id": track_id
        })
        return result is not None and result.get("success", False)
    
    def get_queue(self) -> List[RadioDJTrack]:
        """Get the current queue."""
        result = self._request("GET", "queue")
        if result:
            return [
                RadioDJTrack(
                    id=t["id"],
                    title=t["title"],
                    artist=t["artist"],
                    album=t.get("album", ""),
                    file_path=t.get("path", ""),
                    duration=t.get("duration", 0)
                )
                for t in result.get("tracks", [])
            ]
        
        # Fallback to database
        return self._get_queue_db()
    
    def _get_queue_db(self) -> List[RadioDJTrack]:
        """Get queue from RadioDJ database."""
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT q.ID, q.artist, q.title, s.album, s.path, s.duration
                    FROM queuelist q
                    LEFT JOIN songs s ON q.songID = s.ID
                    ORDER BY q.ID ASC
                """
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                return [
                    RadioDJTrack(
                        id=row['ID'],
                        title=row['title'],
                        artist=row['artist'],
                        album=row.get('album', ''),
                        file_path=row.get('path', ''),
                        duration=row.get('duration', 0)
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get RadioDJ queue: {e}")
            self._db_connection = None
        
        return []
    
    def get_now_playing(self) -> Optional[RadioDJTrack]:
        """Get the currently playing track."""
        result = self._request("GET", "now_playing")
        if result and result.get("track"):
            t = result["track"]
            return RadioDJTrack(
                id=t["id"],
                title=t["title"],
                artist=t["artist"],
                album=t.get("album", ""),
                file_path=t.get("path", ""),
                duration=t.get("duration", 0)
            )
        return None
    
    def get_library_stats(self) -> Dict[str, int]:
        """Get RadioDJ library statistics."""
        conn = self._get_db_connection()
        if not conn:
            return {"total_tracks": 0, "enabled_tracks": 0}
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total FROM songs")
                total = cursor.fetchone()['total']
                
                cursor.execute("SELECT COUNT(*) as enabled FROM songs WHERE enabled = 1")
                enabled = cursor.fetchone()['enabled']
                
                return {"total_tracks": total, "enabled_tracks": enabled}
        except Exception as e:
            logger.error(f"Failed to get RadioDJ stats: {e}")
        
        return {"total_tracks": 0, "enabled_tracks": 0}
    
    def close(self):
        """Close database connection."""
        if self._db_connection:
            try:
                self._db_connection.close()
            except:
                pass
            self._db_connection = None


# Global client instance
radiodj_client = RadioDJClient()
