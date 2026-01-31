"""Task scheduling and management."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.database import SessionLocal
from src.core.state_manager import state_manager
from src.radiodj_integration.sync_service import sync_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Scheduler:
    """Application task scheduler."""

    def __init__(self):
        """Initialize scheduler."""
        self.background_scheduler = BackgroundScheduler()
        logger.info("Scheduler initialized")

    def start(self):
        """Start all scheduled tasks."""
        logger.info("Starting scheduler...")

        # Schedule RadioDJ sync
        self.background_scheduler.add_job(
            func=self._sync_radiodj_job,
            trigger=IntervalTrigger(minutes=2),
            id="sync_radiodj",
            name="Sync to RadioDJ",
            replace_existing=True,
        )

        self.background_scheduler.start()
        state_manager.set_status("running")
        logger.info("Scheduler started")

    def stop(self):
        """Stop scheduler."""
        logger.info("Stopping scheduler...")
        self.background_scheduler.shutdown()
        state_manager.set_status("stopped")
        logger.info("Scheduler stopped")

    def _sync_radiodj_job(self):
        """Job to sync to RadioDJ."""
        logger.info("Running scheduled RadioDJ sync")
        db = SessionLocal()
        try:
            stats = sync_service.sync_approved_requests(db)
            state_manager.increment_stat("requests_synced", stats["synced"])
            state_manager.update_last_sync()
            logger.info("Scheduled sync completed: %s", stats)
        except (ValueError, RuntimeError) as e:
            logger.error("Error in sync job: %s", e)
        finally:
            db.close()


# SINGLETON INSTANCE
scheduler = Scheduler()
