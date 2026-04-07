"""RadioDJ client for API and database integration."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from xml.etree import ElementTree

import requests

from config.settings import DATABASE_CONFIG
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RadioDJTrack:
    """Basic RadioDJ track metadata."""

    id: int
    title: str
    artist: str
    album: str = ""
    file_path: str = ""
    duration: float = 0.0


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
        self.library_path = self.config.get("library_path", "")

        self.db_config = {
            "host": self.config.get("db_host", "localhost"),
            "port": self.config.get("db_port", 3306),
            "database": self.config.get("db_name", "radiodj2"),
            "username": self.config.get("db_username", "root"),
            "password": self.config.get("db_password", ""),
        }
        
        logger.info("RadioDJ client initialized")

    def _build_api_url(self, endpoint: str) -> str:
        """Build a RadioDJ API URL from the configured base URL."""
        return f"{self.api_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def _build_api_params(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build query parameters for the RadioDJ REST plugin."""
        params: Dict[str, Any] = dict(extra or {})
        if self.api_key:
            params.setdefault("auth", self.api_key)
        return params

    def _api_get_json(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Issue a GET request against the RadioDJ plugin and parse JSON."""
        if not self.api_url:
            return None

        try:
            response = requests.get(
                self._build_api_url(endpoint),
                params=self._build_api_params(params),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.debug("RadioDJ JSON endpoint %s unavailable: %s", endpoint, exc)
            return None
        except ValueError as exc:
            logger.warning("RadioDJ JSON endpoint %s returned invalid JSON: %s", endpoint, exc)
            return None

    def _api_get_text(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Issue a GET request against the RadioDJ plugin and return response text."""
        if not self.api_url:
            return None

        try:
            response = requests.get(
                self._build_api_url(endpoint),
                params=self._build_api_params(params),
                timeout=10,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            logger.debug("RadioDJ text endpoint %s unavailable: %s", endpoint, exc)
            return None

    @staticmethod
    def _extract_api_track(payload: Optional[Dict[str, Any]]) -> Optional[RadioDJTrack]:
        """Convert a plugin payload dictionary into a RadioDJTrack."""
        if not payload:
            return None

        track_id = payload.get("id") or payload.get("ID") or payload.get("trackID") or payload.get("TrackID") or 0
        title = payload.get("title") or payload.get("Title") or payload.get("name") or payload.get("Name") or ""
        artist = payload.get("artist") or payload.get("Artist") or payload.get("artists") or ""
        album = payload.get("album") or payload.get("Album") or ""
        file_path = payload.get("path") or payload.get("Path") or payload.get("file_path") or ""
        duration = payload.get("duration") or payload.get("Duration") or 0.0

        if not title and not artist and not track_id:
            return None

        return RadioDJTrack(
            id=int(track_id or 0),
            title=str(title or ""),
            artist=str(artist or ""),
            album=str(album or ""),
            file_path=str(file_path or ""),
            duration=float(duration or 0.0),
        )

    def _extract_now_playing_from_payload(self, payload: Any) -> Optional[RadioDJTrack]:
        """Extract now-playing information from any known plugin payload shape."""
        if isinstance(payload, dict):
            for key in ("NowPlaying", "CurrentTrack", "TrackData", "SongData"):
                track = payload.get(key)
                if isinstance(track, dict):
                    parsed_track = self._extract_api_track(track)
                    if parsed_track:
                        return parsed_track

            parsed_track = self._extract_api_track(payload)
            if parsed_track:
                return parsed_track

        return None

    def _extract_queue_from_payload(self, payload: Any, limit: int) -> List[RadioDJTrack]:
        """Extract queue entries from any known plugin payload shape."""
        if not isinstance(payload, dict):
            return []

        candidates: List[Any] = []
        for key in ("Playlist", "Queue", "Tracks", "Main", "MainPlaylist"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                nested_items = value.get("Items") or value.get("Tracks") or value.get("Playlist")
                if isinstance(nested_items, list):
                    candidates = nested_items
                    break

        tracks: List[RadioDJTrack] = []
        for item in candidates[:limit]:
            if isinstance(item, dict):
                track = self._extract_api_track(item)
                if track:
                    tracks.append(track)

        return tracks

    def _parse_playlist_xml(self, xml_payload: str, limit: int) -> List[RadioDJTrack]:
        """Parse the legacy plugin playlist XML into queue entries."""
        try:
            root = ElementTree.fromstring(xml_payload)
        except ElementTree.ParseError as exc:
            logger.warning("Failed to parse RadioDJ playlist XML: %s", exc)
            return []

        tracks: List[RadioDJTrack] = []
        for element in root.iter():
            children = list(element)
            if not children:
                continue

            payload = {child.tag: (child.text or "") for child in children}
            track = self._extract_api_track(payload)
            if track:
                tracks.append(track)
                if len(tracks) >= limit:
                    break

        return tracks

    def get_track_by_id(self, track_id: int) -> Optional[RadioDJTrack]:
        """Fetch a track by RadioDJ song ID."""
        if not MYSQL_AVAILABLE or track_id <= 0:
            return None

        try:
            conn = mysql.connector.connect(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 3306),
                database=self.db_config.get("database", "radiodj2"),
                user=self.db_config.get("username", "root"),
                password=self.db_config.get("password", ""),
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT ID, artist, title, album, path, duration FROM songs WHERE ID = %s LIMIT 1",
                (track_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if not row:
                return None

            return RadioDJTrack(
                id=int(row["ID"]),
                title=row.get("title", ""),
                artist=row.get("artist", ""),
                album=row.get("album", "") or "",
                file_path=row.get("path", "") or "",
                duration=float(row.get("duration", 0.0) or 0.0),
            )
        except Exception as exc:
            logger.error("Error loading RadioDJ track by id %s: %s", track_id, exc)
            return None

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Normalize text for fuzzy filename matching."""
        return "".join(ch.lower() if ch.isalnum() else " " for ch in value).strip()

    def _search_track_in_filesystem(self, artist: str, title: str) -> bool:
        """Fallback search against a filesystem music library path."""
        if not self.library_path:
            return False

        root = Path(self.library_path)
        if not root.exists() or not root.is_dir():
            return False

        title_key = self._normalize_text(title)
        artist_key = self._normalize_text(artist)
        audio_ext = {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma"}

        try:
            title_only_match: Optional[Path] = None
            for file_path in root.rglob("*"):
                if not file_path.is_file() or file_path.suffix.lower() not in audio_ext:
                    continue

                relative_key = self._normalize_text(str(file_path.relative_to(root)))
                if title_key and title_key in relative_key:
                    if not artist_key or artist_key in relative_key:
                        logger.info("Found track in filesystem library: %s", file_path)
                        return True
                    if title_only_match is None:
                        title_only_match = file_path

            if title_only_match is not None:
                logger.info(
                    "Found title-only match in filesystem library (artist mismatch tolerated): %s",
                    title_only_match,
                )
                return True
        except (OSError, PermissionError) as exc:
            logger.error("Error scanning filesystem library path '%s': %s", root, exc)

        return False

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

        track_id = self.find_track_in_library(artist, title)
        if track_id and track_id > 0:
            try:
                response = requests.get(
                    self._build_api_url("opt"),
                    params=self._build_api_params(
                        {
                            "command": "LoadTrackToBottom",
                            "arg": track_id,
                        }
                    ),
                    timeout=10,
                )
                response.raise_for_status()
                logger.info("Added track via REST plugin /opt: %s - %s (ID=%s)", artist, title, track_id)
                return True
            except requests.RequestException as exc:
                logger.warning("REST plugin /opt queue failed: %s", exc)

        try:
            endpoint = self._build_api_url("addtrack")  # cspell:ignore addtrack
            payload = {
                "artist": artist,
                "title": title,
                "playlist_id": playlist_id or self.default_playlist_id,
                "api_key": self.api_key,
            }

            response = requests.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()

            logger.info("Added track via legacy API: %s - %s", artist, title)
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
        if MYSQL_AVAILABLE:
            try:
                conn = mysql.connector.connect(
                    host=self.db_config.get("host", "localhost"),
                    port=self.db_config.get("port", 3306),
                    database=self.db_config.get("database", "radiodj2"),
                    user=self.db_config.get("username", "root"),
                    password=self.db_config.get("password", ""),
                )
                cursor = conn.cursor()

                # Prefer exact title match first, fall back to fuzzy LIKE
                exact_query = """
                    SELECT ID FROM songs
                    WHERE LOWER(artist) LIKE LOWER(%s)
                    AND LOWER(title) = LOWER(%s)
                    LIMIT 1
                """
                cursor.execute(exact_query, (f"%{artist}%", title))
                result = cursor.fetchone()

                if not result:
                    fuzzy_query = """
                        SELECT ID FROM songs
                        WHERE LOWER(artist) LIKE LOWER(%s)
                        AND LOWER(title) LIKE LOWER(%s)
                        LIMIT 1
                    """
                    cursor.execute(fuzzy_query, (f"%{artist}%", f"%{title}%"))
                    result = cursor.fetchone()

                cursor.close()
                conn.close()

                if result:
                    track_id = cast(int, result[0])
                    logger.info("Found track in RadioDJ DB library: ID=%s", track_id)
                    return track_id
            except Exception as exc:
                logger.error("Error searching RadioDJ database: %s", exc)
        else:
            logger.warning("MySQL connector not available")

        if self._search_track_in_filesystem(artist, title):
            # Sentinel ID for filesystem-only match (not queueable via DB)
            return -1

        logger.warning("Track not found in library: %s - %s", artist, title)
        return None

    def add_track_to_queue_db(self, track_id: int, requested_by: str = "TelegramBot") -> bool:
        """Add track to RadioDJ queue via direct database insert.

        Args:
            track_id: Track ID from RadioDJ library
            requested_by: Name for logging

        Returns:
            True if successful
        """
        if track_id <= 0:
            logger.warning("Cannot queue filesystem-only track without RadioDJ DB ID")
            return False

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

            # Insert into queuelist with ETA set to NOW().
            # Also insert into the requests table so it shows in
            # RadioDJ's Requests panel if enabled.
            queue_query = """
                INSERT INTO queuelist (
                    songID,
                    ETA,
                    duration,
                    artist,
                    associated_artists,
                    title,
                    album
                )
                SELECT
                    ID,
                    NOW(),
                    duration,
                    artist,
                    associated_artists,
                    title,
                    album
                FROM songs
                WHERE ID = %s
            """
            cursor.execute(queue_query, (track_id,))
            queue_rows = cursor.rowcount

            request_query = """
                INSERT INTO requests (songID, username, userIP, message, requested, played)
                VALUES (%s, %s, '127.0.0.1', 'Requested via Telegram', NOW(), 0)
            """
            cursor.execute(request_query, (track_id, requested_by))

            conn.commit()
            cursor.close()
            conn.close()

            if queue_rows and queue_rows > 0:
                logger.info("Added track %s to RadioDJ queue and requests", track_id)
                return True

            logger.warning(
                "Queue insert reported no affected rows for track %s; not marking as queued",
                track_id,
            )
            return False

        except Exception as exc:
            logger.error("Error adding track to queue: %s", exc)
            return False

    def validate_connection(self) -> Dict[str, bool]:
        """Validate RadioDJ connections.

        Returns:
            Dictionary with connection status
        """
        status = {"api_available": False, "database_available": False, "filesystem_available": False}

        # Check API
        if self.api_url:
            api_checks = (
                lambda: self._api_get_json("npjson") is not None,
                lambda: self._api_get_text("p") is not None,
                lambda: self._api_get_json("Status") is not None,
            )
            status["api_available"] = any(check() for check in api_checks)

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
                cursor = conn.cursor()
                cursor.execute("SHOW TABLES LIKE 'songs'")
                has_songs = cursor.fetchone() is not None
                cursor.execute("SHOW TABLES LIKE 'queuelist'")
                has_queue = cursor.fetchone() is not None
                cursor.close()
                conn.close()
                status["database_available"] = has_songs and has_queue
            except Exception:
                status["database_available"] = False

        if self.library_path:
            root = Path(self.library_path)
            status["filesystem_available"] = root.exists() and root.is_dir()

        logger.info("RadioDJ connection status: %s", status)
        return status

    def get_now_playing(self) -> Optional[RadioDJTrack]:
        """Return the most recently played track from RadioDJ history."""
        for endpoint in ("npjson", "Status"):
            payload = self._api_get_json(endpoint)
            track = self._extract_now_playing_from_payload(payload)
            if track:
                return track

        if not MYSQL_AVAILABLE:
            return None

        try:
            conn = mysql.connector.connect(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 3306),
                database=self.db_config.get("database", "radiodj2"),
                user=self.db_config.get("username", "root"),
                password=self.db_config.get("password", ""),
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT trackID, artist, title, album, duration
                FROM history
                ORDER BY date_played DESC, ID DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if not row:
                return None

            return RadioDJTrack(
                id=int(row.get("trackID", 0) or 0),
                title=row.get("title", ""),
                artist=row.get("artist", ""),
                album=row.get("album", "") or "",
                duration=float(row.get("duration", 0.0) or 0.0),
            )
        except Exception as exc:
            logger.error("Error loading RadioDJ now playing: %s", exc)
            return None

    def get_queue(self, limit: int = 10) -> List[RadioDJTrack]:
        """Return the upcoming RadioDJ queue entries."""
        payload = self._api_get_json("npjson")
        tracks = self._extract_queue_from_payload(payload, limit)
        if tracks:
            return tracks

        xml_payload = self._api_get_text("p")
        if xml_payload:
            tracks = self._parse_playlist_xml(xml_payload, limit)
            if tracks:
                return tracks

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
            cursor.execute(
                """
                SELECT ID, songID, artist, title, album, duration
                FROM queuelist
                ORDER BY ID ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            return [
                RadioDJTrack(
                    id=int(row.get("songID", 0) or 0),
                    title=row.get("title", ""),
                    artist=row.get("artist", ""),
                    album=row.get("album", "") or "",
                    duration=float(row.get("duration", 0.0) or 0.0),
                )
                for row in rows
            ]
        except Exception as exc:
            logger.error("Error loading RadioDJ queue: %s", exc)
            return []
    
    def search_songs(self, query: str, limit: int = 10) -> list:
        """Search for songs in RadioDJ library.
        
        Args:
            query: Search term (artist or title)
            limit: Max results
            
        Returns:
            List of matching songs
        """
        if self.api_url and self.api_key:
            api_results = self._api_get_json(
                "Tracks",
                {
                    "command": "Search",
                    "arg": json.dumps(
                        {
                            "Keyword": query,
                            "Subcategory": 0,
                            "Genre": 0,
                            "StartIndex": 1,
                            "ResultsToShow": limit,
                        },
                        separators=(",", ":"),
                    ),
                },
            )

            if isinstance(api_results, list):
                return api_results
            if isinstance(api_results, dict):
                for key in ("Tracks", "Items", "Results"):
                    value = api_results.get(key)
                    if isinstance(value, list):
                        return value

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
