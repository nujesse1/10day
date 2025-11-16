"""
Strike management and deadline checking logic
Handles logging strikes when habits are missed and managing punishment assignment
"""
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from app.utils.timezone import get_pacific_now, get_pacific_today_date
from . import repository

logger = logging.getLogger(__name__)


def log_strike(habit_id: int, reason: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Log a strike for a habit and automatically assign punishment

    Args:
        habit_id: The habit ID
        reason: Reason for strike ('missed_deadline', 'no_proof', etc.)
        notes: Optional additional context

    Returns:
        Dict with strike data, strike count, and punishment result
    """
    # Import here to avoid circular dependency
    from .punishments import assign_punishment

    today = get_pacific_today_date()

    # Log the strike using repository
    strike_data = repository.create_strike(habit_id, today, reason, notes)

    # Get today's total strike count
    strike_count = get_today_strike_count()

    # Automatically assign punishment based on strike count
    punishment_result = assign_punishment(strike_count)

    return {
        "status": "success",
        "data": strike_data,
        "strike_count": strike_count,
        "punishment": punishment_result
    }


def get_strike_count(habit_id: Optional[int] = None, days: Optional[int] = None) -> Dict[str, Any]:
    """
    Get strike count for a habit or all habits with habit details

    Args:
        habit_id: Optional habit ID (if None, returns counts for all habits)
        days: Optional number of days to look back (if None, returns all time)

    Returns:
        Dict with strike counts and details including habit names
    """
    # Get all habits for joining
    habits = repository.get_all_habits()
    habit_map = {h["id"]: h for h in habits}

    # Determine date range
    if days is not None:
        cutoff_date = date.today() - timedelta(days=days)
    else:
        cutoff_date = None

    # Get strikes based on filters
    if habit_id is not None:
        strikes = repository.get_strikes_for_habit(habit_id)
        # Filter by date if needed
        if cutoff_date:
            strikes = [s for s in strikes if date.fromisoformat(s["date"]) >= cutoff_date]
    else:
        # Get all habits and aggregate strikes
        all_habits = repository.get_all_habits()
        strikes = []
        for h in all_habits:
            habit_strikes = repository.get_strikes_for_habit(h["id"])
            if cutoff_date:
                habit_strikes = [s for s in habit_strikes if date.fromisoformat(s["date"]) >= cutoff_date]
            strikes.extend(habit_strikes)

    # Group by habit_id and include habit details
    strikes_by_habit = {}
    for strike in strikes:
        hid = strike["habit_id"]
        if hid not in strikes_by_habit:
            habit_info = habit_map.get(hid, {})
            strikes_by_habit[hid] = {
                "habit_id": hid,
                "habit_title": habit_info.get("title", f"Unknown (ID: {hid})"),
                "strikes": [],
                "strike_count": 0
            }
        strikes_by_habit[hid]["strikes"].append(strike)
        strikes_by_habit[hid]["strike_count"] += 1

    # Convert to list for easier consumption
    strikes_list = list(strikes_by_habit.values())

    return {
        "status": "success",
        "total_strikes": len(strikes),
        "habits_with_strikes": strikes_list,
        "all_strikes": strikes,
        "strike_count": len(strikes)  # For backwards compatibility
    }


def get_habit_strikes(habit_id: int) -> List[Dict[str, Any]]:
    """
    Get all strikes for a specific habit

    Args:
        habit_id: The habit ID

    Returns:
        List of strike records
    """
    return repository.get_strikes_for_habit(habit_id)


def get_today_strike_count() -> int:
    """
    Get the total number of strikes logged today (across all habits)

    Returns:
        Total strike count for today
    """
    today = get_pacific_today_date()
    strikes = repository.get_strikes_for_date(today)
    return len(strikes)


def _get_deadline_check_context() -> Dict[str, Any]:
    """
    Gather all context needed for deadline checking

    Returns:
        Dict containing today, current_time, habits, reminded_ids, striked_ids
    """
    now_pacific = get_pacific_now()
    today = now_pacific.date()
    current_time = now_pacific.time()

    # Get today's habits with completions
    habits = repository.get_habits_with_completions(today)

    # Get today's deadline reminders
    reminders = repository.get_reminders_for_date(today)
    reminded_habit_ids = {r["habit_id"] for r in reminders if r["reminder_type"] == "deadline"}

    # Get today's strikes to avoid duplicates
    existing_strikes = repository.get_strikes_for_date(today)
    already_striked_ids = {s["habit_id"] for s in existing_strikes if s["reason"] == "missed_deadline"}

    return {
        "today": today,
        "current_time": current_time,
        "habits": habits,
        "reminded_ids": reminded_habit_ids,
        "striked_ids": already_striked_ids
    }


def _should_log_strike(habit: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Determine if a strike should be logged for this habit

    Args:
        habit: Habit dict with id, title, deadline_time, completed
        context: Context from _get_deadline_check_context

    Returns:
        True if strike should be logged, False otherwise
    """
    habit_id = habit["id"]
    deadline_time_str = habit.get("deadline_time")
    completed = habit.get("completed", False)

    # Skip if no deadline set
    if not deadline_time_str:
        return False

    # Parse deadline time
    deadline_time = datetime.strptime(deadline_time_str, "%H:%M:%S").time()

    # Check if deadline has passed
    if context["current_time"] < deadline_time:
        return False

    # Skip if already completed
    if completed:
        return False

    # Skip if we haven't sent a deadline reminder yet
    if habit_id not in context["reminded_ids"]:
        return False

    # Skip if we already logged a strike today
    if habit_id in context["striked_ids"]:
        return False

    return True


def _log_and_notify_strike(habit: Dict[str, Any], context: Dict[str, Any],
                           notification_service=None) -> Dict[str, Any]:
    """
    Log a strike for a habit and optionally send notification

    Args:
        habit: Habit dict with id, title, deadline_time
        context: Context from _get_deadline_check_context
        notification_service: Optional NotificationService instance

    Returns:
        Strike result dict
    """
    habit_id = habit["id"]
    habit_title = habit["title"]
    deadline_time_str = habit.get("deadline_time")

    logger.info(f"[DEADLINE CHECK] Logging strike for missed deadline: {habit_title}")

    strike_result = log_strike(
        habit_id=habit_id,
        reason="missed_deadline",
        notes=f"Deadline {deadline_time_str} missed on {context['today']}"
    )

    logger.info(f"[DEADLINE CHECK] Strike logged for habit_id={habit_id} ({habit_title})")

    # Send notification if service provided
    if notification_service:
        strike_count = strike_result.get("strike_count", 0)
        punishment_info = strike_result.get("punishment", {})
        notification_service.send_strike_notification(habit_title, strike_count, punishment_info)

    return strike_result


def check_missed_deadlines(send_notification_callback=None):
    """
    Check for habits that missed their deadline and log strikes
    Called periodically (e.g., every hour or at end of day)

    Args:
        send_notification_callback: Optional function to send WhatsApp notifications
                                   Should accept message string as parameter

    Logic:
    - Find habits where deadline_time has passed
    - Check if habit was completed
    - If not completed AND deadline reminder was sent, log a strike
    """
    try:
        from app.services.notifications.service import NotificationService

        logger.info("[DEADLINE CHECK] Checking for missed deadlines...")

        # Create notification service if callback provided
        notification_service = NotificationService(send_notification_callback) if send_notification_callback else None

        # Gather context
        context = _get_deadline_check_context()

        strikes_logged = 0

        for habit in context["habits"]:
            # Check if strike should be logged
            if not _should_log_strike(habit, context):
                continue

            # Log strike and optionally send notification
            try:
                _log_and_notify_strike(habit, context, notification_service)
                strikes_logged += 1
            except Exception as e:
                logger.error(f"[DEADLINE CHECK] Failed to log strike for habit_id={habit['id']}: {e}")

        if strikes_logged > 0:
            logger.info(f"[DEADLINE CHECK] Logged {strikes_logged} strike(s) for missed deadlines")
        else:
            logger.info("[DEADLINE CHECK] No missed deadlines found")

    except Exception as e:
        logger.error(f"[DEADLINE CHECK] Error in check_missed_deadlines: {e}", exc_info=True)
