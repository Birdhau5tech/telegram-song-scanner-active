"""MusicBrainz API client with rate limiting and caching."""

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, cast

import musicbrainzngs

from config.settings import MUSIC_MATCHING_CONFIG
from src.utils.cache import cache_manager
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

# CONFIGURE MUSICBRAINZ
musicbrainzngs.set_useragent(
    MUSIC_MATCHING_CONFIG["musicbrainz"]["user_agent"],  # type: ignore[index]
    "1.0.0",
    "https://github.com/KiloMusician/whatsapp-song-scanner",
)


class MusicBrainzClient:
    """MusicBrainz API client with caching and rate limiting."""

    def __init__(self):
        """Initialize MusicBrainz client."""
        self.rate_limiter = RateLimiter(
            calls=1, period=MUSIC_MATCHING_CONFIG["musicbrainz"]["rate_limit_per_second"]
        )
        self.cache_duration = timedelta(
            hours=MUSIC_MATCHING_CONFIG["musicbrainz"]["cache_duration_hours"]
        )
        logger.info("MusicBrainz client initialized")

    def search_song(self, song_title: str, artist_name: Optional[str] = None) -> List[Dict]:
        """Search for a song using MusicBrainz API.

        Args:
            song_title: The title of the song to search for
            artist_name: Optional artist name to refine search

        Returns:
            List of matching song dictionaries
        """
        # GENERATE CACHE KEY
        cache_key = self._generate_cache_key(song_title, artist_name)

        # CHECK CACHE FIRST
        cached_result = cache_manager.get(cache_key)
        if cached_result:
            logger.debug("Cache hit for: %s", song_title)
            return cast(List[Dict], json.loads(cached_result))

        # ENFORCE RATE LIMIT
        self.rate_limiter.wait()

        try:
            # CONSTRUCT SEARCH QUERY - Try exact match first
            query_parts = [f'recording:"{song_title}"']
            if artist_name:
                query_parts.append(f'artist:"{artist_name}"')

            search_query = " AND ".join(query_parts)
            logger.info("Searching MusicBrainz: %s", search_query)

            # PERFORM SEARCH WITH RETRY LOGIC
            result = self._search_with_retry(search_query)

            # If no results with exact artist match, try broader search
            if not result.get("recording-list") and artist_name:
                logger.info("No results with exact artist match, trying broader search")
                search_query = f'recording:"{song_title}"'
                logger.info("Searching MusicBrainz: %s", search_query)
                result = self._search_with_retry(search_query)

            # PROCESS AND FORMAT RESULTS
            formatted_results = self._format_search_results(result)

            # CACHE THE RESULTS
            cache_manager.set(
                key=cache_key,
                value=json.dumps(formatted_results),
                ttl=int(self.cache_duration.total_seconds()),
            )

            logger.info("Found %s results for: %s", len(formatted_results), song_title)
            return cast(List[Dict], formatted_results)

        except musicbrainzngs.NetworkError as exc:
            logger.error("MusicBrainz network error: %s", exc)
            return []
        except musicbrainzngs.ResponseError as exc:
            logger.error("MusicBrainz response error: %s", exc)
            return []
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Unexpected error in search_song: %s", exc)
            return []

    def _search_with_retry(self, query: str, max_retries: int = 3) -> Dict:
        """Search with retry logic for network failures."""
        for attempt in range(max_retries):
            try:
                result = musicbrainzngs.search_recordings(query=query, limit=10, offset=0)
                return cast(Dict, result)
            except musicbrainzngs.NetworkError:
                if attempt == max_retries - 1:
                    raise
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2, 4, 6 seconds
                logger.warning("Network error, retrying in %s seconds...", wait_time)
                time.sleep(wait_time)
        return {}

    def _extract_artist_info(self, recording: Dict) -> List[Dict]:
        """Extract artist information from a recording.

        Args:
            recording: Recording data from MusicBrainz

        Returns:
            List of artist information dictionaries
        """
        artists = []
        if "artist-credit" in recording:
            for credit in recording["artist-credit"]:
                if isinstance(credit, dict) and "artist" in credit:
                    artist = credit["artist"]
                    artists.append(
                        {
                            "id": artist.get("id", ""),
                            "name": artist.get("name", ""),
                            "sort_name": artist.get("sort-name", ""),
                        }
                    )
        return artists

    def _extract_release_info(self, recording: Dict) -> List[Dict]:
        """Extract release information from a recording.

        Args:
            recording: Recording data from MusicBrainz

        Returns:
            List of release information dictionaries (limited to 3)
        """
        releases = []
        if "release-list" in recording:
            for release in recording["release-list"][:3]:  # Limit to 3 releases
                releases.append(
                    {
                        "id": release.get("id", ""),
                        "title": release.get("title", ""),
                        "date": release.get("date", ""),
                    }
                )
        return releases

    def _format_search_results(self, result: Dict) -> List[Dict]:
        """Format MusicBrainz results into a consistent structure."""
        formatted: List[Dict] = []

        if "recording-list" not in result:
            return formatted

        for recording in result["recording-list"]:
            # EXTRACT ARTIST INFORMATION
            artists = self._extract_artist_info(recording)

            # EXTRACT RELEASE INFORMATION
            releases = self._extract_release_info(recording)

            # BUILD FORMATTED RESULT
            formatted.append(
                {
                    "musicbrainz_id": recording.get("id", ""),
                    "title": recording.get("title", ""),
                    "length": recording.get("length", 0),
                    "artist_credits": artists,
                    "releases": releases,
                    "score": int(recording.get("ext:score", 0)),
                    "tags": [tag["name"] for tag in recording.get("tag-list", [])],
                    "disambiguation": recording.get("disambiguation", ""),
                    "metadata_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        return formatted

    def get_recording_details(self, recording_id: str) -> Optional[Dict]:
        """Get detailed information for a specific recording."""
        cache_key = f"recording_details_{recording_id}"

        cached_result = cache_manager.get(cache_key)
        if cached_result:
            return cast(Optional[Dict], json.loads(cached_result))

        self.rate_limiter.wait()

        try:
            result = musicbrainzngs.get_recording_by_id(
                recording_id, includes=["artists", "releases", "tags"]
            )

            formatted_details = self._format_recording_details(result)

            cache_manager.set(
                key=cache_key,
                value=json.dumps(formatted_details),
                ttl=int(self.cache_duration.total_seconds()),
            )

            return cast(Optional[Dict], formatted_details)

        except (KeyError, ValueError, TypeError, musicbrainzngs.MusicBrainzError) as e:
            logger.error("Error getting recording details: %s", e)
            return None

    def _format_recording_details(self, result: Dict) -> Dict:
        """Format recording details."""
        if "recording" not in result:
            return {}

        recording = result["recording"]
        return {
            "id": recording.get("id", ""),
            "title": recording.get("title", ""),
            "length": recording.get("length", 0),
            "disambiguation": recording.get("disambiguation", ""),
        }

    def _generate_cache_key(self, song_title: str, artist_name: Optional[str] = None) -> str:
        """Generate a unique cache key for search queries."""
        key_string = f"{song_title.lower().strip()}"
        if artist_name:
            key_string += f"_{artist_name.lower().strip()}"

        return f"musicbrainz_search_{hashlib.md5(key_string.encode()).hexdigest()}"


# SINGLETON INSTANCE
musicbrainz_client = MusicBrainzClient()
