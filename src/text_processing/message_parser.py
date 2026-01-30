"""Extract song titles and artists from messages."""

import re
from typing import Dict, List

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MessageParser:
    """Parse messages to extract song requests."""

    def __init__(self):
        """Initialize message parser with patterns."""
        # Song request patterns with named groups
        self.patterns = [
            # "play Song by Artist"
            (
                re.compile(
                    r'play\s+["\']?(?P<title>[^"\']+?)["\']?\s+by\s+(?P<artist>[^\'\".]+)',
                    re.IGNORECASE,
                ),
                "play_by",
            ),
            # "request: Artist - Song"
            (
                re.compile(
                    r'request:?\s+(?P<artist>[^-]+)\s*-\s*(?P<title>[^"\'.]+)',
                    re.IGNORECASE,
                ),
                "request_dash",
            ),
            # "can you play: Song"
            (
                re.compile(r'can\s+you\s+play:?\s+["\']?(?P<title>[^"\']+)["\']?', re.IGNORECASE),
                "can_you_play",
            ),
            # "song? Title"
            (
                re.compile(r'song\??\s+["\']?(?P<title>[^"\']+)["\']?', re.IGNORECASE),
                "song_question",
            ),
            # "I want to hear Song by Artist"
            (
                re.compile(
                    r'(?:i\s+)?want\s+to\s+hear\s+["\']?(?P<title>[^"\']+?)["\']?\s+by\s+'
                    r'(?P<artist>[^"\'.]+)',
                    re.IGNORECASE,
                ),
                "want_to_hear",
            ),
            # "Artist - Song"
            (
                re.compile(
                    r'^(?P<artist>[^-]+)\s*-\s*(?P<title>[^"\'.]+)$',
                    re.IGNORECASE | re.MULTILINE,
                ),
                "simple_dash",
            ),
            # "Song - Artist" per-line
            (
                re.compile(
                    r'^(?P<title>[^-]+?)\s*-\s*(?P<artist>[^"\'.]+)$',
                    re.IGNORECASE | re.MULTILINE,
                ),
                "simple_dash_reverse",
            ),
            # "Song by Artist" (without keywords)
            (
                re.compile(
                    r'(?P<title>[^"\']+?)\s+by\s+(?P<artist>[^"\'.]+)',
                    re.IGNORECASE,
                ),
                "title_by_artist",
            ),
            # Quoted song title
            (re.compile(r'["\'](?P<title>[^"\']{3,})["\']', re.IGNORECASE), "quoted"),
        ]

    def parse(self, text: str) -> List[Dict]:
        """Parse message text to extract song requests.

        Args:
            text: Cleaned message text

        Returns:
            List of extracted song candidates with metadata
        """
        if not text or len(text) < 3:
            return []

        candidates = []

        seen = set()

        for pattern, method_name in self.patterns:
            for match in pattern.finditer(text):
                groups = match.groupdict()

                title = groups.get("title", "").strip() if groups.get("title") else None
                artist = groups.get("artist", "").strip() if groups.get("artist") else None

                # Only add if we have at least a title
                if not title:
                    continue

                dedupe_key = (title.lower(), (artist or "").lower())
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                candidate = {
                    "title": title,
                    "artist": artist,
                    "original_phrase": match.group(0),
                    "extraction_method": method_name,
                    "confidence": self._calculate_confidence(method_name, groups),
                }

                candidates.append(candidate)
                logger.debug("Extracted candidate: %s", candidate)

        return candidates

    def _calculate_confidence(self, method: str, groups: Dict) -> float:
        """Calculate confidence score for extraction.

        Args:
            method: Extraction method name
            groups: Regex match groups

        Returns:
            Confidence score (0-100)
        """
        base_scores = {
            "play_by": 95,
            "request_dash": 90,
            "can_you_play": 85,
            "want_to_hear": 90,
            "simple_dash": 80,
            "song_question": 75,
            "title_by_artist": 85,  # High confidence for explicit "by" format
            "quoted": 70,
        }

        score = base_scores.get(method, 50)

        # Boost if we have both title and artist
        if groups.get("title") and groups.get("artist"):
            score = min(100, score + 5)

        # Reduce if title is very short
        if groups.get("title") and len(groups["title"]) < 3:
            score -= 20

        # Reduce if title is very long (likely not a song)
        if groups.get("title") and len(groups["title"]) > 100:
            score -= 30

        return max(0, min(100, score))


# SINGLETON INSTANCE
message_parser = MessageParser()
