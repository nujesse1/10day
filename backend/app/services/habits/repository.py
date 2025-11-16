"""
Habits Repository - Centralized database access layer
All Supabase queries for habits, completions, strikes, and reminders
"""
from datetime import date
from typing import List, Dict, Any, Optional
import logging

from app.core.dependencies import supabase_client as supabase
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


# ============================================================================
# HABITS TABLE
# ============================================================================

def get_all_habits() -> List[Dict[str, Any]]:
    """
    Get all habits from the database

    Returns:
        List of habit dictionaries

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("habits").select("*").execute()
        return result.data
    except Exception as e:
        logger.error(f"Database error fetching habits: {e}")
        raise DatabaseError(f"Failed to fetch habits: {e}")


def get_habit_by_id(habit_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a single habit by ID

    Args:
        habit_id: The habit ID

    Returns:
        Habit dictionary or None if not found

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("habits").select("*").eq("id", habit_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Database error fetching habit {habit_id}: {e}")
        raise DatabaseError(f"Failed to fetch habit: {e}")


def create_habit(title: str, start_time: str, deadline_time: str,
                 punishment_habit: bool = False, auto_delete_at: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new habit

    Args:
        title: Habit title
        start_time: Start time in HH:MM format
        deadline_time: Deadline time in HH:MM format
        punishment_habit: Whether this is a punishment habit
        auto_delete_at: Optional date string (YYYY-MM-DD) for auto-deletion

    Returns:
        Created habit data

    Raises:
        DatabaseError: If insert fails
    """
    try:
        habit_data = {
            "title": title,
            "start_time": start_time,
            "deadline_time": deadline_time,
            "punishment_habit": punishment_habit
        }
        if auto_delete_at:
            habit_data["auto_delete_at"] = auto_delete_at

        result = supabase.table("habits").insert(habit_data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error creating habit: {e}")
        raise DatabaseError(f"Failed to create habit: {e}")


def update_habit(habit_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a habit

    Args:
        habit_id: The habit ID
        update_data: Dictionary of fields to update

    Returns:
        Updated habit data

    Raises:
        DatabaseError: If update fails
    """
    try:
        result = supabase.table("habits").update(update_data).eq("id", habit_id).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error updating habit {habit_id}: {e}")
        raise DatabaseError(f"Failed to update habit: {e}")


def delete_habit(habit_id: int) -> Dict[str, Any]:
    """
    Delete a habit

    Args:
        habit_id: The habit ID

    Returns:
        Deleted habit data

    Raises:
        DatabaseError: If delete fails
    """
    try:
        result = supabase.table("habits").delete().eq("id", habit_id).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error deleting habit {habit_id}: {e}")
        raise DatabaseError(f"Failed to delete habit: {e}")


def get_expired_punishment_habits(today: date) -> List[Dict[str, Any]]:
    """
    Get all punishment habits that should be deleted (auto_delete_at <= today)

    Args:
        today: Current date

    Returns:
        List of expired punishment habits

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("habits")\
            .select("*")\
            .eq("punishment_habit", True)\
            .lte("auto_delete_at", str(today))\
            .execute()
        return result.data
    except Exception as e:
        logger.error(f"Database error fetching expired punishment habits: {e}")
        raise DatabaseError(f"Failed to fetch expired punishment habits: {e}")


# ============================================================================
# HABIT_COMPLETIONS TABLE
# ============================================================================

def get_completions_for_date(target_date: date) -> List[Dict[str, Any]]:
    """
    Get all habit completions for a specific date

    Args:
        target_date: The date to fetch completions for

    Returns:
        List of completion dictionaries

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("habit_completions")\
            .select("*")\
            .eq("date", str(target_date))\
            .execute()
        return result.data
    except Exception as e:
        logger.error(f"Database error fetching completions for {target_date}: {e}")
        raise DatabaseError(f"Failed to fetch completions: {e}")


def get_completion_for_habit_and_date(habit_id: int, target_date: date) -> Optional[Dict[str, Any]]:
    """
    Get completion for a specific habit and date

    Args:
        habit_id: The habit ID
        target_date: The date

    Returns:
        Completion dictionary or None if not found

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("habit_completions")\
            .select("*")\
            .eq("habit_id", habit_id)\
            .eq("date", str(target_date))\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Database error fetching completion for habit {habit_id} on {target_date}: {e}")
        raise DatabaseError(f"Failed to fetch completion: {e}")


def create_completion(habit_id: int, target_date: date, completed: bool = False,
                     proof_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new completion entry

    Args:
        habit_id: The habit ID
        target_date: The date
        completed: Whether the habit is completed
        proof_path: Optional path to proof image

    Returns:
        Created completion data

    Raises:
        DatabaseError: If insert fails
    """
    try:
        completion_data = {
            "habit_id": habit_id,
            "date": str(target_date),
            "completed": completed
        }
        if proof_path:
            completion_data["proof_path"] = proof_path

        result = supabase.table("habit_completions").insert(completion_data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error creating completion: {e}")
        raise DatabaseError(f"Failed to create completion: {e}")


def update_completion(habit_id: int, target_date: date, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a completion entry

    Args:
        habit_id: The habit ID
        target_date: The date
        update_data: Dictionary of fields to update

    Returns:
        Updated completion data

    Raises:
        DatabaseError: If update fails
    """
    try:
        result = supabase.table("habit_completions")\
            .update(update_data)\
            .eq("habit_id", habit_id)\
            .eq("date", str(target_date))\
            .execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error updating completion for habit {habit_id} on {target_date}: {e}")
        raise DatabaseError(f"Failed to update completion: {e}")


# ============================================================================
# REMINDER_LOG TABLE
# ============================================================================

def get_reminders_for_date(target_date: date) -> List[Dict[str, Any]]:
    """
    Get all sent reminders for a specific date

    Args:
        target_date: The date to fetch reminders for

    Returns:
        List of reminder log entries

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("reminder_log")\
            .select("*")\
            .eq("date", str(target_date))\
            .execute()
        return result.data
    except Exception as e:
        logger.error(f"Database error fetching reminders for {target_date}: {e}")
        raise DatabaseError(f"Failed to fetch reminders: {e}")


def create_reminder_log(habit_id: int, target_date: date, reminder_type: str) -> Dict[str, Any]:
    """
    Log a sent reminder

    Args:
        habit_id: The habit ID
        target_date: The date
        reminder_type: Type of reminder ('start' or 'deadline')

    Returns:
        Created reminder log entry

    Raises:
        DatabaseError: If insert fails
    """
    try:
        result = supabase.table("reminder_log").insert({
            "habit_id": habit_id,
            "date": str(target_date),
            "reminder_type": reminder_type
        }).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error creating reminder log: {e}")
        raise DatabaseError(f"Failed to create reminder log: {e}")


# ============================================================================
# STRIKES TABLE
# ============================================================================

def get_strikes_for_habit(habit_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get all strikes for a specific habit

    Args:
        habit_id: The habit ID
        limit: Optional limit on number of results

    Returns:
        List of strike dictionaries

    Raises:
        DatabaseError: If query fails
    """
    try:
        query = supabase.table("strikes").select("*").eq("habit_id", habit_id).order("created_at", desc=True)
        if limit:
            query = query.limit(limit)
        result = query.execute()
        return result.data
    except Exception as e:
        logger.error(f"Database error fetching strikes for habit {habit_id}: {e}")
        raise DatabaseError(f"Failed to fetch strikes: {e}")


def get_strikes_for_date(target_date: date) -> List[Dict[str, Any]]:
    """
    Get all strikes for a specific date

    Args:
        target_date: The date

    Returns:
        List of strike dictionaries

    Raises:
        DatabaseError: If query fails
    """
    try:
        result = supabase.table("strikes")\
            .select("*")\
            .eq("date", str(target_date))\
            .execute()
        return result.data
    except Exception as e:
        logger.error(f"Database error fetching strikes for {target_date}: {e}")
        raise DatabaseError(f"Failed to fetch strikes: {e}")


def create_strike(habit_id: int, target_date: date, reason: str,
                 notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new strike entry

    Args:
        habit_id: The habit ID
        target_date: The date
        reason: Reason for the strike
        notes: Optional additional notes

    Returns:
        Created strike data

    Raises:
        DatabaseError: If insert fails
    """
    try:
        strike_data = {
            "habit_id": habit_id,
            "date": str(target_date),
            "reason": reason
        }
        if notes:
            strike_data["notes"] = notes

        result = supabase.table("strikes").insert(strike_data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Database error creating strike: {e}")
        raise DatabaseError(f"Failed to create strike: {e}")


# ============================================================================
# COMBINED QUERIES (for performance)
# ============================================================================

def get_habits_with_completions(target_date: date) -> List[Dict[str, Any]]:
    """
    Get all habits with their completion status for a specific date

    Args:
        target_date: The date to check completions for

    Returns:
        List of habits with completion info merged

    Raises:
        DatabaseError: If query fails
    """
    habits = get_all_habits()
    if not habits:
        return []

    completions = get_completions_for_date(target_date)
    completion_map = {c["habit_id"]: c for c in completions}

    # Merge completion data into habits
    result = []
    for habit in habits:
        completion = completion_map.get(habit["id"])
        result.append({
            **habit,
            "completed": completion["completed"] if completion else False,
            "proof_path": completion.get("proof_path") if completion else None,
            "completion_id": completion["id"] if completion else None
        })

    return result
