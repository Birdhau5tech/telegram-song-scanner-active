"""RadioDJ client for API and database integration."""

from pathlib import Path
from typing import Dict, Optional, cast

import requests

from config.settings import DATABASE_CONFIG
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Try to import MySQL connector
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.warning("mysql-connector-python not installed - RadioDJ DB access disabled")


class RadioDJClient:
    """Client for RadioDJ integration."""

    def __init__(self):
        """Initialize RadioDJ client."""
        self.config = DATABASE_CONFIG.get("radiodj", {})
        self.api_url = self.config.get("api_url", "")
        self.api_key = self.config.get("api_key", "")
        self.default_playlist_id = self.config.get("default_playlist_id", 1)
        
        # RadioDJ uses its own database (radiodj2), not the app's database
        # Use same host/credentials but different database name
        mariadb = DATABASE_CONFIG.get("mariadb", {})
        self.db_config = {
            "host": mariadb.get("host", "localhost"),
            "port": mariadb.get("port", 3306),
            "database": "radiodj2",  # RadioDJ's database, not song_scanner
            "username": mariadb.get("username", "root"),
            "password": mariadb.get("password", ""),
        }
        
        logger.info("RadioDJ client initialized")

    def add_track_via_api(self, artist: str, title: str, playlist_id: Optional[int] = None) -> bool:
        """Add track to RadioDJ queue via API.

        Args:
            artist: Artist name
            title: Song title
            playlist_id: Playlist ID (optional)

        Returns:
            True if successful
        """
        if not self.api_url or not self.api_key:
            logger.warning("RadioDJ API not configured")
            return False

        try:
            endpoint = f"{self.api_url}/addtrack"  # cspell:ignore addtrack
            payload = {
                "artist": artist,
                "title": title,
                "playlist_id": playlist_id or self.default_playlist_id,
                "api_key": self.api_key,
            }

            response = requests.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()

            logger.info("Added track via API: %s - %s", artist, title)
            return True
        except requests.RequestException as exc:
            logger.error("Failed to add track via API: %s", exc)
            return False

    def find_track_in_library(self, artist: str, title: str) -> Optional[int]:
        """Find track ID in RadioDJ library database.

        Args:
            artist: Artist name
            title: Song title

        Returns:
            Track ID if found, None otherwise
        """
        if not MYSQL_AVAILABLE:
            logger.warning("MySQL connector not available")
            return None

        try:
            conn = mysql.connector.connect(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 3306),
                database=self.db_config.get("database", "radiodj2"),
                user=self.db_config.get("username", "root"),
                password=self.db_config.get("password", ""),
            )
            cursor = conn.cursor()

            # Query for track in RadioDJ songs table
            # RadioDJ uses 'songs' table with 'artist' and 'title' columns
            query = """
                SELECT ID FROM songs
                WHERE LOWER(artist) LIKE LOWER(%s)
                AND LOWER(title) LIKE LOWER(%s)
                LIMIT 1
            """

            cursor.execute(query, (f"%{artist}%", f"%{title}%"))
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                track_id = cast(int, result[0])
                logger.info("Found track in library: ID=%s", track_id)
                return track_id
            else:
                logger.warning("Track not found in library: %s - %s", artist, title)
                return None

        except Exception as exc:
            logger.error("Error searching RadioDJ database: %s", exc)
            return None

    def add_track_to_queue_db(self, track_id: int) -> bool:
        """Add track to RadioDJ queue via direct database access.

        Args:
            track_id: Track ID from RadioDJ library

        Returns:
            True if successful
        """
        if not MYSQL_AVAILABLE:
            logger.warning("MySQL connector not available")
            return False

        try:
            conn = mysql.connector.connect(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 3306),
                database=self.db_config.get("database", "radiodj2"),
                user=self.db_config.get("username", "root"),
                password=self.db_config.get("password", ""),
            )
            cursor = conn.cursor()

            # Insert into RadioDJ queuelist table
            # RadioDJ uses 'queuelist' table for the playback queue
            query = """
                INSERT INTO queuelist (songID, requestID, played, artistID)
                SELECT %s, 0, 0, artist_id FROM songs WHERE ID = %s
            """

            cursor.execute(query, (track_id, track_id))
            conn.commit()
            cursor.close()
            conn.close()

            logger.info("Added track %s to RadioDJ queue", track_id)
            return True

        except Exception as exc:
            logger.error("Error adding track to queue: %s", exc)
            return False
            return False

    def validate_connection(self) -> Dict[str, bool]:
        """Validate RadioDJ connections.

        Returns:
            Dictionary with connection status
        """
        status = {"api_available": False, "database_available": False}

        # Check API
        if self.api_url:
            try:
                response = requests.get(f"{self.api_url}/health", timeout=5)
                status["api_available"] = response.status_code == 200
            except requests.RequestException:
                status["api_available"] = False

        # Check database
        if MYSQL_AVAILABLE:
            try:
                conn = mysql.connector.connect(
                    host=self.db_config.get("host", "localhost"),
                    port=self.db_config.get("port", 3306),
                    database=self.db_config.get("database", "radiodj2"),
                    user=self.db_config.get("username", "root"),
                    password=self.db_config.get("password", ""),
                    connect_timeout=5,
                )
                conn.close()
                status["database_available"] = True
            except Exception:
                status["database_available"] = False

        logger.info("RadioDJ connection status: %s", status)
        return status
    
    def search_songs(self, query: str, limit: int = 10) -> list:
        """Search for songs in RadioDJ library.
        
        Args:
            query: Search term (artist or title)
            limit: Max results
            
        Returns:
            List of matching songs
        """
        if not MYSQL_AVAILABLE:
            return []
            
        try:
            conn = mysql.connector.connect(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 3306),
                database=self.db_config.get("database", "radiodj2"),
                user=self.db_config.get("username", "root"),
                password=self.db_config.get("password", ""),
            )
            cursor = conn.cursor(dictionary=True)
            
            sql = """
                SELECT ID, artist, title, duration, path
                FROM songs
                WHERE artist LIKE %s OR title LIKE %s
                LIMIT %s
            """
            cursor.execute(sql, (f"%{query}%", f"%{query}%", limit))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
        except Exception as exc:
            logger.error("Error searching songs: %s", exc)
            return []


# SINGLETON INSTANCE
radiodj_client = RadioDJClient()
