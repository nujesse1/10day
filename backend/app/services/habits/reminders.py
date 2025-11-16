"""
Habit reminder scheduling and tracking
Handles reminder logic for start times and deadlines
"""
from datetime import datetime
from typing import List, Dict, Any
import logging

from app.utils.timezone import get_pacific_today_date, get_pacific_current_time
from . import repository

logger = logging.getLogger(__name__)


def get_habits_needing_reminders() -> List[Dict[str, Any]]:
    """
    Get habits that need reminders sent right now.
    Returns list of dicts with habit info and reminder_type ('start' or 'deadline')

    Logic:
    - Current time >= start_time AND habit not complete AND start reminder not sent today
    - Current time >= deadline_time AND habit not complete AND deadline reminder not sent today
    """
    # Use Pacific timezone for all time comparisons
    today = get_pacific_today_date()
    current_time = get_pacific_current_time()

    # Get all habits
    habits = repository.get_all_habits()
    if not habits:
        return []

    # Get today's completions
    completions = repository.get_completions_for_date(today)
    completion_map = {c["habit_id"]: c for c in completions}

    # Get today's sent reminders
    reminders = repository.get_reminders_for_date(today)

    # Create set of (habit_id, reminder_type) tuples for already sent reminders
    sent_reminders = {(r["habit_id"], r["reminder_type"]) for r in reminders}

    needs_reminder = []

    for habit in habits:
        habit_id = habit["id"]

        # Check if habit is already completed
        completion = completion_map.get(habit_id)
        if completion and completion.get("completed"):
            continue  # Skip completed habits

        # Check start time reminder
        start_time_str = habit.get("start_time")
        if start_time_str:
            start_time = datetime.strptime(start_time_str, "%H:%M:%S").time()
            if current_time >= start_time and (habit_id, "start") not in sent_reminders:
                needs_reminder.append({
                    "habit_id": habit_id,
                    "habit_title": habit["title"],
                    "reminder_type": "start",
                    "scheduled_time": start_time_str
                })

        # Check deadline time reminder
        deadline_time_str = habit.get("deadline_time")
        if deadline_time_str:
            deadline_time = datetime.strptime(deadline_time_str, "%H:%M:%S").time()
            if current_time >= deadline_time and (habit_id, "deadline") not in sent_reminders:
                needs_reminder.append({
                    "habit_id": habit_id,
                    "habit_title": habit["title"],
                    "reminder_type": "deadline",
                    "scheduled_time": deadline_time_str
                })

    return needs_reminder


def mark_reminder_sent(habit_id: int, reminder_type: str) -> Dict[str, Any]:
    """
    Mark a reminder as sent in the reminder_log

    Args:
        habit_id: The habit ID
        reminder_type: 'start' or 'deadline'

    Returns:
        Dict with status and data
    """
    today = get_pacific_today_date()

    repository.create_reminder_log(habit_id, today, reminder_type)

    return {
        "status": "success",
        "habit_id": habit_id,
        "reminder_type": reminder_type,
        "date": str(today)
    }
