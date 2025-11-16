"""
Timezone Utilities - Centralized timezone handling
"""
from datetime import datetime
import pytz


# Application timezone - Pacific Time
PACIFIC_TZ = pytz.timezone('America/Los_Angeles')


def get_pacific_tz():
    """
    Get the Pacific timezone object

    Returns:
        pytz timezone for America/Los_Angeles
    """
    return PACIFIC_TZ


def get_pacific_now() -> datetime:
    """
    Get current datetime in Pacific timezone

    Returns:
        Timezone-aware datetime object in Pacific timezone
    """
    return datetime.now(PACIFIC_TZ)


def get_pacific_today_date():
    """
    Get today's date in Pacific timezone

    Returns:
        date object for today in Pacific timezone
    """
    return get_pacific_now().date()


def get_pacific_current_time():
    """
    Get current time in Pacific timezone

    Returns:
        time object for current time in Pacific timezone
    """
    return get_pacific_now().time()
