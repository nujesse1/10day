"""
FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from app.routes import habits, health, whatsapp, chat
from app.services.scheduler import start_scheduler, stop_scheduler

# Configure logging
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
