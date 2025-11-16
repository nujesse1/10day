"""
Scheduler Service - Background scheduler lifecycle management
Handles starting, stopping, and configuring the APScheduler instance
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.core.constants import SCHEDULER_CHECK_INTERVAL_SECONDS
from .jobs import check_all, cleanup_punishment_habits

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def start_scheduler():
    """
    Start the background scheduler
    Runs checks every N seconds (configured in constants)
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already running")
        return

    scheduler = BackgroundScheduler()

    # Run both checks every N seconds (configured in constants)
    scheduler.add_job(
        func=check_all,
        trigger=IntervalTrigger(seconds=SCHEDULER_CHECK_INTERVAL_SECONDS),
        id='habit_check',
        name='Check reminders and missed deadlines',
        replace_existing=True
    )

    # Run punishment cleanup daily at 11:59 PM
    scheduler.add_job(
        func=cleanup_punishment_habits,
        trigger=CronTrigger(hour=23, minute=59),
        id='punishment_cleanup',
        name='Cleanup expired punishment habits',
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Scheduler started - checking every {SCHEDULER_CHECK_INTERVAL_SECONDS} seconds, cleanup at 11:59 PM")


def stop_scheduler():
    """Stop the background scheduler"""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
