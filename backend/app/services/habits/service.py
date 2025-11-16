"""
Habits Service - Business logic for habit management
Handles creating, reading, updating, and deleting habits
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List
import json
import logging

from app.core.dependencies import openai_client
from app.core.constants import LLM_MODEL_DEFAULT
from app.core.exceptions import (
    HabitNotFoundError,
    InvalidHabitDataError,
    DatabaseError,
    ExternalServiceError
)
from app.utils.prompts import format_habit_matching_prompt, LLM_HABIT_MATCHING_SYSTEM_PROMPT
from . import repository

logger = logging.getLogger(__name__)


def find_habit_by_llm(user_input: str, existing_habits: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Use LLM to match user input against existing habits using semantic similarity.

    Args:
        user_input: The user's natural language description of a habit
        existing_habits: List of existing habit dictionaries with 'id' and 'title' fields

    Returns:
        The best matching habit dict or None if no good match exists

    Raises:
        ExternalServiceError: If LLM API call fails
    """
    if not existing_habits:
        return None

    habit_list = "\n".join([f"{h['id']}: {h['title']}" for h in existing_habits])
    prompt = format_habit_matching_prompt(user_input, habit_list)

    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL_DEFAULT,
            messages=[
                {"role": "system", "content": LLM_HABIT_MATCHING_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        habit_id = result.get("habit_id")

        if habit_id is None:
            return None

        # Find and return the matching habit
        for habit in existing_habits:
            if habit["id"] == habit_id:
                return habit

        return None
    except Exception as e:
        logger.error(f"LLM matching error: {e}")
        raise ExternalServiceError(f"Failed to match habit using LLM: {e}")


def add_habit(title: str, start_time: str, deadline_time: str) -> Dict[str, Any]:
    """
    Add a new habit with required schedule times

    Args:
        title: Habit title
        start_time: Time in HH:MM format (24-hour) when habit should be started
        deadline_time: Time in HH:MM format (24-hour) when habit must be completed by

    Returns:
        Dict with status, message, and created habit data

    Raises:
        InvalidHabitDataError: If time formats are invalid
        DatabaseError: If database operation fails
    """
    # Validate time formats
    try:
        datetime.strptime(start_time, "%H:%M")
    except ValueError:
        raise InvalidHabitDataError(f"Invalid start_time format: {start_time}. Use HH:MM (24-hour)")

    try:
        datetime.strptime(deadline_time, "%H:%M")
    except ValueError:
        raise InvalidHabitDataError(f"Invalid deadline_time format: {deadline_time}. Use HH:MM (24-hour)")

    # Create habit using repository
    habit_data = repository.create_habit(title, start_time, deadline_time)

    return {
        "status": "success",
        "message": f"Habit '{title}' added successfully with start time {start_time} and deadline {deadline_time}",
        "data": habit_data
    }


def remove_habit_by_title(title: str) -> Dict[str, Any]:
    """
    Remove a habit by title using LLM semantic matching

    Args:
        title: User's description of the habit to remove

    Returns:
        Dict with status, message, and deleted habit data

    Raises:
        HabitNotFoundError: If no habits exist or no matching habit found
        DatabaseError: If database operation fails
    """
    # Get all habits
    habits = repository.get_all_habits()

    if not habits:
        raise HabitNotFoundError("No habits found")

    # Use LLM to find matching habit
    matched_habit = find_habit_by_llm(title, habits)

    if not matched_habit:
        raise HabitNotFoundError(f"No habit matching '{title}' found")

    # Delete the habit using repository
    repository.delete_habit(matched_habit["id"])

    return {
        "status": "success",
        "message": f"Habit '{matched_habit['title']}' removed successfully",
        "habit_id": matched_habit["id"],
        "habit_title": matched_habit["title"]
    }


def complete_habit_by_title(title: str, proof_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Mark a habit as complete for today by title (with LLM matching)

    Args:
        title: User's description of the habit
        proof_path: Optional path to proof image

    Returns:
        Dict with status, habit name, and completion data

    Raises:
        HabitNotFoundError: If no matching habit found
        DatabaseError: If database operation fails
    """
    today = date.today()

    # Get all habits
    habits = repository.get_all_habits()

    if not habits:
        raise HabitNotFoundError("No habits found")

    # Use LLM to find matching habit
    matched_habit = find_habit_by_llm(title, habits)

    if not matched_habit:
        raise HabitNotFoundError(f"No habit matching '{title}' found")

    habit_id = matched_habit["id"]

    # Check if completion entry exists for today
    existing = repository.get_completion_for_habit_and_date(habit_id, today)

    if not existing:
        # Create completion entry
        repository.create_completion(habit_id, today, completed=False)

    # Update the completion
    update_data = {"completed": True}
    if proof_path:
        update_data["proof_path"] = proof_path

    completion_data = repository.update_completion(habit_id, today, update_data)

    return {
        "status": "success",
        "habit": matched_habit["title"],
        "completed": True,
        "proof": proof_path,
        "data": completion_data
    }


def get_today_habits() -> Dict[str, Any]:
    """
    Get all habits with today's completion status

    Returns:
        Dict with status, date, and list of habits with completion info
    """
    today = date.today()

    # Get habits with completions using repository
    habits = repository.get_habits_with_completions(today)

    return {
        "status": "success",
        "date": str(today),
        "habits": habits
    }


def get_daily_summary() -> Dict[str, Any]:
    """
    Get today's summary of habit completion including totals and completion rate

    Returns:
        Dict with status, date, total_habits, completed, missed, completion_rate,
        completed_habits list, and missed_habits list
    """
    today = date.today()

    # Get all habits
    habits = repository.get_all_habits()
    total_habits = len(habits)

    if total_habits == 0:
        return {
            "status": "success",
            "date": str(today),
            "total_habits": 0,
            "completed": 0,
            "missed": 0,
            "completion_rate": 0.0,
            "details": []
        }

    # Get today's completions
    completions = repository.get_completions_for_date(today)
    completion_map = {c["habit_id"]: c for c in completions}

    completed_count = sum(1 for c in completions if c["completed"])
    missed_habits = []
    completed_habits = []

    for habit in habits:
        completion = completion_map.get(habit["id"])
        if completion and completion["completed"]:
            completed_habits.append(habit["title"])
        else:
            missed_habits.append(habit["title"])

    completion_rate = (completed_count / total_habits * 100) if total_habits > 0 else 0

    return {
        "status": "success",
        "date": str(today),
        "total_habits": total_habits,
        "completed": completed_count,
        "missed": len(missed_habits),
        "completion_rate": round(completion_rate, 2),
        "completed_habits": completed_habits,
        "missed_habits": missed_habits
    }


def set_habit_schedule(title: str, start_time: Optional[str] = None, deadline_time: Optional[str] = None) -> Dict[str, Any]:
    """
    Set schedule times for a habit

    Args:
        title: Habit title (will use LLM matching)
        start_time: Time in HH:MM format (24-hour) or None to keep current
        deadline_time: Time in HH:MM format (24-hour) or None to keep current

    Returns:
        Dict with status, message, and updated habit data

    Raises:
        HabitNotFoundError: If no habits exist or no matching habit found
        InvalidHabitDataError: If time formats are invalid
        DatabaseError: If database operation fails
    """
    # Get all habits
    habits = repository.get_all_habits()

    if not habits:
        raise HabitNotFoundError("No habits found")

    # Use LLM to find matching habit
    matched_habit = find_habit_by_llm(title, habits)

    if not matched_habit:
        raise HabitNotFoundError(f"No habit matching '{title}' found")

    # Validate time formats
    update_data = {}
    if start_time is not None:
        try:
            # Validate time format
            datetime.strptime(start_time, "%H:%M")
            update_data["start_time"] = start_time
        except ValueError:
            raise InvalidHabitDataError(f"Invalid start_time format: {start_time}. Use HH:MM (24-hour)")

    if deadline_time is not None:
        try:
            # Validate time format
            datetime.strptime(deadline_time, "%H:%M")
            update_data["deadline_time"] = deadline_time
        except ValueError:
            raise InvalidHabitDataError(f"Invalid deadline_time format: {deadline_time}. Use HH:MM (24-hour)")

    if not update_data:
        raise InvalidHabitDataError("Must provide at least one time (start_time or deadline_time)")

    # Update the habit using repository
    habit_data = repository.update_habit(matched_habit["id"], update_data)

    return {
        "status": "success",
        "message": f"Schedule updated for habit '{matched_habit['title']}'",
        "habit": matched_habit["title"],
        "start_time": update_data.get("start_time"),
        "deadline_time": update_data.get("deadline_time"),
        "data": habit_data
    }
