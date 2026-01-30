"""Fuzzy string matching for song titles and artists."""

from typing import Any, Dict, List, Optional, Tuple, cast

from thefuzz import fuzz
import re

from config.settings import MUSIC_MATCHING_CONFIG
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FuzzyMatcher:
    """Fuzzy string matching for songs."""

    def __init__(self):
        """Initialize fuzzy matcher."""
        self.config: Dict[str, Any] = cast(
            Dict[str, Any], MUSIC_MATCHING_CONFIG.get("fuzzy_matching", {})
        )
        self.min_score: int = int(self.config.get("min_match_score", 80))
        
        # Common artist name corrections for typos
        self.artist_corrections = {
            "hiatus koyote": "hiatus kaiyote",
            "haitus kaiyote": "hiatus kaiyote",
            "haitus koyote": "hiatus kaiyote",
            "hiatus kaiyote": "hiatus kaiyote",  # Already correct
        }
        
        logger.info(
            "Fuzzy matcher initialized with min_score=%s",
            self.min_score,
        )

    def match_title(self, query: str, candidate: str) -> int:
        """Match song titles using fuzzy matching.

        Args:
            query: Query title
            candidate: Candidate title

        Returns:
            Match score (0-100)
        """
        if not query or not candidate:
            return 0

        # Normalize both strings with title-specific cleanup
        query_norm = self._normalize_title(query)
        candidate_norm = self._normalize_title(candidate)

        # Take the best of multiple fuzzy strategies to handle variants
        scores = [
            fuzz.token_sort_ratio(query_norm, candidate_norm),
            fuzz.token_set_ratio(query_norm, candidate_norm),
            fuzz.partial_ratio(query_norm, candidate_norm),
        ]

        return int(max(scores))

    def match_artist(self, query: str, candidate: str) -> int:
        """Match artist names using fuzzy matching.

        Args:
            query: Query artist
            candidate: Candidate artist

        Returns:
            Match score (0-100)
        """
        if not query or not candidate:
            return 0

        # Apply typo corrections to query
        query_norm = self._normalize_artist(query)
        corrected_query = self.artist_corrections.get(query_norm, query_norm)
        
        # Normalize both strings with artist-specific cleanup
        candidate_norm = self._normalize_artist(candidate)

        # Use a combination and take the best score
        scores = [
            fuzz.token_set_ratio(corrected_query, candidate_norm),
            fuzz.partial_ratio(corrected_query, candidate_norm),
            fuzz.token_sort_ratio(corrected_query, candidate_norm),
        ]

        return int(max(scores))

    def rank_candidates(
        self, query_title: str, query_artist: str, candidates: List[Dict]
    ) -> List[Tuple[Dict, float]]:
        """Rank candidates by match quality.

        Returns (candidate, final_score) tuples sorted by score.
        """
        scored_candidates: List[Tuple[Dict, float]] = []

        for candidate in candidates:
            candidate_title = candidate.get("title", "")

            # Primary artist name (supports MusicBrainz and simple dicts)
            candidate_artist = ""
            if candidate.get("artist_credits"):
                candidate_artist = candidate["artist_credits"][0].get("name", "")
            elif candidate.get("artist"):
                candidate_artist = candidate.get("artist", "")

            # Scores
            title_score = self.match_title(query_title, candidate_title)

            artist_score = 0
            if query_artist and candidate_artist:
                artist_score = self.match_artist(query_artist, candidate_artist)

            combined_score = (
                (title_score * 0.7) + (artist_score * 0.3) if query_artist else title_score
            )

            # Small bonus for exact normalized title/artist matches
            try:
                if self._normalize_title(query_title) == self._normalize_title(candidate_title):
                    combined_score = min(100.0, combined_score + 5)
                if query_artist and candidate_artist:
                    if self._normalize_artist(query_artist) == self._normalize_artist(
                        candidate_artist
                    ):
                        combined_score = min(100.0, combined_score + 5)
            except Exception:
                pass

            # MusicBrainz search score bonus
            mb_score = candidate.get("score", 50)
            final_score = (combined_score * 0.8) + (mb_score * 0.2)
            final_score = min(100.0, final_score)

            scored_candidates.append(
                (
                    {
                        **candidate,
                        "title_match_score": title_score,
                        "artist_match_score": artist_score,
                        "combined_match_score": combined_score,
                        "final_score": final_score,
                    },
                    final_score,
                )
            )

        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        filtered = [c for c in scored_candidates if c[1] >= self.min_score]

        max_candidates: int = int(self.config.get("max_candidates", 5))
        return filtered[:max_candidates]

    def _normalize_title(self, s: str) -> str:
        """Normalize a song title by removing common noise.

        Removes bracketed parts, trailing descriptors (remaster, live, edit), and extra whitespace.
        """
        if not s:
            return ""

        s = s.lower().strip()

        # Remove content in brackets or parentheses
        s = re.sub(r"\[[^\]]*\]", "", s)
        s = re.sub(r"\([^\)]*\)", "", s)

        # Remove featuring/feat parts
        s = re.sub(r"\b(feat\.|featuring|ft\.)\b.*$", "", s).strip()

        # Remove common trailing descriptors
        descriptors = (
            r"remaster(?:ed)?(\s*\d{2,4})?",
            r"radio\s+edit",
            r"single\s+version",
            r"album\s+version",
            r"video\s+edit",
            r"lyrics",
            r"official\s+video",
            r"live",
            r"mono",
            r"stereo",
            r"mix",
            r"edit",
            r"version",
        )
        s = re.sub(r"\s*-\s*(?:" + "|".join(descriptors) + r").*$", "", s)

        # Remove extra punctuation (keep spaces, word chars, and hyphens/apostrophes)
        s = re.sub(r"[^\w\s\-']", " ", s)
        s = " ".join(s.split())
        return s

    def _normalize_artist(self, s: str) -> str:
        """Normalize an artist string by removing feature credits and punctuation."""
        if not s:
            return ""
        s = s.lower().strip()
        # Drop featuring/feat credits
        s = re.sub(r"\b(feat\.|featuring|ft\.)\b.*$", "", s)
        # Replace & with 'and' for consistency
        s = s.replace("&", " and ")
        s = re.sub(r"[^\w\s\-']", " ", s)
        s = " ".join(s.split())
        return s

    def get_best_match(
        self, query_title: str, query_artist: str, candidates: List[Dict]
    ) -> Tuple[Optional[Dict], float]:
        """Get the best matching candidate."""
        ranked = self.rank_candidates(query_title, query_artist, candidates)

        if not ranked:
            return None, 0.0

        best_candidate, confidence = ranked[0]

        logger.info(
            "Best match: %s (score=%.2f)",
            best_candidate["title"],
            confidence,
        )

        return best_candidate, confidence


# SINGLETON INSTANCE


fuzzy_matcher = FuzzyMatcher()
