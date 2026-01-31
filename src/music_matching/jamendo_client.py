"""Jamendo API client for track search."""

from typing import Dict, List, Optional

import requests
from requests import RequestException

from config.settings import MUSIC_MATCHING_CONFIG
from src.utils.logger import get_logger

logger = get_logger(__name__)


class JamendoClient:
    """Lightweight Jamendo client for read-only search."""

    def __init__(self):
        jamendo_cfg = MUSIC_MATCHING_CONFIG.get("jamendo", {})
        self.client_id = jamendo_cfg.get("client_id", "")
        self.client_secret = jamendo_cfg.get("client_secret", "")
        self.base_url = jamendo_cfg.get("base_url", "https://api.jamendo.com/v3.0")
        self.timeout = jamendo_cfg.get("timeout_seconds", 8.0)
        self.max_results = jamendo_cfg.get("max_results", 10)

    def _build_params(self, title: str, artist: Optional[str]) -> Dict:
        params: Dict[str, str] = {
            "client_id": self.client_id,
            "format": "json",
            "limit": str(self.max_results),
            "include": "musicinfo",
            "search": title,
        }
        if artist:
            params["artist_name"] = artist
        if self.client_secret:
            params["client_secret"] = self.client_secret
        return params

    def search_song(self, title: str, artist: Optional[str] = None) -> List[Dict]:
        """Search Jamendo tracks and normalize results."""
        if not self.client_id:
            logger.debug("Jamendo client_id missing; skipping lookup")
            return []

        try:
            resp = requests.get(
                f"{self.base_url}/tracks",
                params=self._build_params(title, artist),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json() or {}
            results = data.get("results") or []
            normalized: List[Dict] = []
            for item in results:
                normalized.append(
                    {
                        "title": item.get("name"),
                        "artist": item.get("artist_name"),
                        "jamendo_id": item.get("id"),
                        "duration": item.get("duration"),
                        "musicinfo": item.get("musicinfo"),
                        "raw": item,
                    }
                )
            logger.info("Jamendo returned %s tracks for '%s'", len(normalized), title)
            return normalized
        except RequestException as exc:
            logger.warning("Jamendo lookup failed: %s", exc)
            return []
        except (ValueError, TypeError) as exc:
            logger.warning("Jamendo response parse failed: %s", exc)
            return []


# Singleton instance
jamendo_client = JamendoClient()
