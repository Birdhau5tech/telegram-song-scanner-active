"""Sync MariaDB song requests with RadioDJ."""

import time
from typing import Dict, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.operations import RequestOperations
from src.radiodj_integration.playlist_manager import playlist_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SyncService:
    """Sync song requests to RadioDJ."""

    def __init__(self):
        """Initialize sync service."""
        self.playlist_manager = playlist_manager
        self.retry_delays_seconds = [60, 120, 240]

    def process_request(self, db: Session, request) -> bool:
        """Process a single approved request through the queue protocol."""
        try:
            matched_song = request.matched_song

            artist = matched_song.artist_name or "Unknown"
            title = matched_song.song_title

            if getattr(request, "radiodj_track_id", None):
                logger.info("Skipping already queued request %s", request.id)
                return True

            active_request = RequestOperations.start_queue_attempt(
                db,
                cast(int, request.id),
                method="api_db",
            )
            if not active_request:
                return False

            track_id = self.playlist_manager.add_song_to_playlist(
                artist=artist,
                title=title,
                use_api=True,
            )

            if track_id is not None:
                track_id_int = int(track_id) if track_id > 0 else None
                RequestOperations.mark_queue_success(
                    db,
                    cast(int, request.id),
                    method="api_db",
                    radiodj_track_id=track_id_int,
                )
                logger.info("Synced request %s: %s - %s", request.id, artist, title)
                return True

            RequestOperations.record_queue_failure(
                db,
                cast(int, request.id),
                error_message="queue_add_failed",
                method="api_db",
                retry_delays_seconds=self.retry_delays_seconds,
            )
            logger.warning("Failed to sync request %s: %s - %s", request.id, artist, title)
            return False

        except (SQLAlchemyError, ValueError, RuntimeError) as exc:
            RequestOperations.record_queue_failure(
                db,
                cast(int, request.id),
                error_message=str(exc),
                method="api_db",
                retry_delays_seconds=self.retry_delays_seconds,
            )
            logger.error("Error syncing request %s: %s", request.id, exc)
            return False

    def sync_approved_requests(self, db: Session, limit: int = 50) -> Dict[str, int]:
        """Sync approved requests to RadioDJ.

        Args:
            db: Database session
            limit: Maximum requests to process

        Returns:
            Dictionary with sync statistics
        """
        logger.info("Starting sync of approved requests to RadioDJ")

        approved_requests = RequestOperations.get_queue_candidates(db, limit)

        if not approved_requests:
            logger.info("No approved requests to sync")
            return {"synced": 0, "failed": 0}

        stats = {"synced": 0, "failed": 0}

        for request in approved_requests:
            if self.process_request(db, request):
                stats["synced"] += 1
            else:
                stats["failed"] += 1

        logger.info("Sync completed: %s", stats)
        return stats

    def run_continuous_sync(self, db: Session, interval_seconds: int = 60):
        """Run continuous sync (for scheduler).

        Args:
            db: Database session
            interval_seconds: Sync interval
        """
        logger.info("Starting continuous sync with %ss interval", interval_seconds)

        while True:
            try:
                self.sync_approved_requests(db)
                time.sleep(interval_seconds)
            except (SQLAlchemyError, ValueError, RuntimeError) as exc:
                logger.error("Error in continuous sync: %s", exc)
                time.sleep(interval_seconds)


# SINGLETON INSTANCE
sync_service = SyncService()
