"""
FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from app.routes import habits, health, whatsapp, chat
from app.services.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Silence noisy third-party loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup/shutdown events
    """
    # Startup
    try:
        start_scheduler()
        logger.info("✓ Habit reminder scheduler started")
    except Exception as e:
        logger.warning(f"Could not start scheduler: {e}")

    yield

    # Shutdown
    try:
        stop_scheduler()
        logger.info("✓ Habit reminder scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Drill Sergeant API",
    version="0.1.0",
    lifespan=lifespan
)

# Register routes
app.include_router(health.router)
app.include_router(habits.router)
app.include_router(chat.router)
app.include_router(whatsapp.router)
