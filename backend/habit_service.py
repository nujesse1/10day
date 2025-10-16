"""
Habit Service - Core business logic for habit management
Shared between FastAPI endpoints and chat engine to avoid HTTP deadlock
"""
from datetime import date, datetime, time
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import crypto punishment module
try:
    from crypto_punishment import send_usdc_punishment
    CRYPTO_ENABLED = True
    logger.info("Crypto punishment module loaded successfully")
except ImportError as e:
    logger.warning(f"Crypto punishment module not available: {e}")
    CRYPTO_ENABLED = False

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def find_habit_by_llm(user_input: str, existing_habits: list) -> Optional[dict]:
    """
    Use LLM to match user input against existing habits
    Returns the best matching habit or None if no good match
    """
    if not existing_habits:
        return None

    habit_list = "\n".join([f"{h['id']}: {h['title']}" for h in existing_habits])

    prompt = f"""Given the user input: "{user_input}"
And these existing habits:
{habit_list}

Return ONLY a JSON object with the best matching habit ID, or null if no good match exists:
{{"habit_id": <number or null>}}

Match semantically - consider synonyms, abbreviations, and different phrasings."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a semantic matching assistant. Return only valid JSON."},
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
        print(f"LLM matching error: {e}")
        return None


def add_habit(title: str, start_time: str, deadline_time: str) -> Dict[str, Any]:
    """
    Add a new habit with required schedule times

    Args:
        title: Habit title
        start_time: Time in HH:MM format (24-hour) when habit should be started
        deadline_time: Time in HH:MM format (24-hour) when habit must be completed by
    """
    # Validate time formats
    try:
        datetime.strptime(start_time, "%H:%M")
    except ValueError:
        raise ValueError(f"Invalid start_time format: {start_time}. Use HH:MM (24-hour)")

    try:
        datetime.strptime(deadline_time, "%H:%M")
    except ValueError:
        raise ValueError(f"Invalid deadline_time format: {deadline_time}. Use HH:MM (24-hour)")

    # Insert habit with schedule times
    result = supabase.table("habits").insert({
        "title": title,
        "start_time": start_time,
        "deadline_time": deadline_time
    }).execute()

    return {
        "status": "success",
        "message": f"Habit '{title}' added successfully with start time {start_time} and deadline {deadline_time}",
        "data": result.data
    }


def remove_habit_by_title(title: str) -> Dict[str, Any]:
    """Remove a habit by title (with LLM matching)"""
    # Get all habits
    habits = supabase.table("habits").select("*").execute()

    if not habits.data:
        raise ValueError("No habits found")

    # Use LLM to find matching habit
    matched_habit = find_habit_by_llm(title, habits.data)

    if not matched_habit:
        raise ValueError(f"No habit matching '{title}' found")

    # Delete the habit
    result = supabase.table("habits").delete().eq("id", matched_habit["id"]).execute()

    return {
        "status": "success",
        "message": f"Habit '{matched_habit['title']}' removed successfully",
        "data": result.data
    }


def complete_habit_by_title(title: str, proof_path: Optional[str] = None) -> Dict[str, Any]:
    """Mark a habit as complete for today by title (with LLM matching)"""
    today = date.today()

    # Get all habits
    habits = supabase.table("habits").select("*").execute()

    if not habits.data:
        raise ValueError("No habits found")

    # Use LLM to find matching habit
    matched_habit = find_habit_by_llm(title, habits.data)

    if not matched_habit:
        raise ValueError(f"No habit matching '{title}' found")

    habit_id = matched_habit["id"]

    # Check if completion entry exists for today
    existing = supabase.table("habit_completions")\
        .select("*")\
        .eq("habit_id", habit_id)\
        .eq("date", str(today))\
        .execute()

    if not existing.data:
        # Auto-generate completion entry
        supabase.table("habit_completions").insert({
            "habit_id": habit_id,
            "date": str(today),
            "completed": False
        }).execute()

    # Update the completion
    update_data = {"completed": True}
    if proof_path:
        update_data["proof_path"] = proof_path

    result = supabase.table("habit_completions")\
        .update(update_data)\
        .eq("habit_id", habit_id)\
        .eq("date", str(today))\
        .execute()

    return {
        "status": "success",
        "habit": matched_habit["title"],
        "completed": True,
        "proof": proof_path,
        "data": result.data
    }


def get_today_habits() -> Dict[str, Any]:
    """Get all habits with today's completion status"""
    today = date.today()

    # Get all habits
    habits = supabase.table("habits").select("*").execute()

    if not habits.data:
        return {
            "status": "success",
            "date": str(today),
            "habits": []
        }

    # Get today's completions
    completions = supabase.table("habit_completions")\
        .select("*")\
        .eq("date", str(today))\
        .execute()

    # Create a map of habit_id to completion
    completion_map = {c["habit_id"]: c for c in completions.data}

    # Combine habits with their completion status
    result = []
    for habit in habits.data:
        completion = completion_map.get(habit["id"])
        result.append({
            "id": habit["id"],
            "title": habit["title"],
            "completed": completion["completed"] if completion else False,
            "proof_path": completion.get("proof_path") if completion else None,
            "completion_id": completion["id"] if completion else None,
            "start_time": habit.get("start_time"),
            "deadline_time": habit.get("deadline_time")
        })

    return {
        "status": "success",
        "date": str(today),
        "habits": result
    }


def set_habit_schedule(title: str, start_time: Optional[str] = None, deadline_time: Optional[str] = None) -> Dict[str, Any]:
    """
    Set schedule times for a habit

    Args:
        title: Habit title (will use LLM matching)
        start_time: Time in HH:MM format (24-hour) or None to clear
        deadline_time: Time in HH:MM format (24-hour) or None to clear
    """
    # Get all habits
    habits = supabase.table("habits").select("*").execute()

    if not habits.data:
        raise ValueError("No habits found")

    # Use LLM to find matching habit
    matched_habit = find_habit_by_llm(title, habits.data)

    if not matched_habit:
        raise ValueError(f"No habit matching '{title}' found")

    # Validate time formats
    update_data = {}
    if start_time is not None:
        try:
            # Validate time format
            datetime.strptime(start_time, "%H:%M")
            update_data["start_time"] = start_time
        except ValueError:
            raise ValueError(f"Invalid start_time format: {start_time}. Use HH:MM (24-hour)")

    if deadline_time is not None:
        try:
            # Validate time format
            datetime.strptime(deadline_time, "%H:%M")
            update_data["deadline_time"] = deadline_time
        except ValueError:
            raise ValueError(f"Invalid deadline_time format: {deadline_time}. Use HH:MM (24-hour)")

    if not update_data:
        raise ValueError("Must provide at least one time (start_time or deadline_time)")

    # Update the habit
    result = supabase.table("habits")\
        .update(update_data)\
        .eq("id", matched_habit["id"])\
        .execute()

    return {
        "status": "success",
        "message": f"Schedule updated for habit '{matched_habit['title']}'",
        "habit": matched_habit["title"],
        "start_time": update_data.get("start_time"),
        "deadline_time": update_data.get("deadline_time"),
        "data": result.data
    }


def get_habits_needing_reminders() -> List[Dict[str, Any]]:
    """
    Get habits that need reminders sent right now.
    Returns list of dicts with habit info and reminder_type ('start' or 'deadline')

    Logic:
    - Current time >= start_time AND habit not complete AND start reminder not sent today
    - Current time >= deadline_time AND habit not complete AND deadline reminder not sent today
    """
    import pytz

    # Use Pacific timezone for all time comparisons
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific_tz)
    today = now_pacific.date()
    current_time = now_pacific.time()

    # Get all habits with schedules
    habits = supabase.table("habits").select("*").execute()

    if not habits.data:
        return []

    # Get today's completions
    completions = supabase.table("habit_completions")\
        .select("*")\
        .eq("date", str(today))\
        .execute()

    completion_map = {c["habit_id"]: c for c in completions.data}

    # Get today's sent reminders
    reminders = supabase.table("reminder_log")\
        .select("*")\
        .eq("date", str(today))\
        .execute()

    # Create set of (habit_id, reminder_type) tuples for already sent reminders
    sent_reminders = {(r["habit_id"], r["reminder_type"]) for r in reminders.data}

    needs_reminder = []

    for habit in habits.data:
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
    """
    today = date.today()

    result = supabase.table("reminder_log").insert({
        "habit_id": habit_id,
        "date": str(today),
        "reminder_type": reminder_type
    }).execute()

    return {
        "status": "success",
        "data": result.data
    }


def log_strike(habit_id: int, reason: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Log a strike for a habit and automatically assign punishment

    Args:
        habit_id: The habit ID
        reason: Reason for strike ('missed_deadline', 'no_proof', etc.)
        notes: Optional additional context
    """
    today = date.today()

    # Log the strike
    result = supabase.table("strikes").insert({
        "habit_id": habit_id,
        "date": str(today),
        "reason": reason,
        "notes": notes
    }).execute()

    # Get today's total strike count
    strike_count = get_today_strike_count()

    # Automatically assign punishment based on strike count
    punishment_result = assign_punishment(strike_count)

    return {
        "status": "success",
        "data": result.data,
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
    query = supabase.table("strikes").select("*")

    if habit_id is not None:
        query = query.eq("habit_id", habit_id)

    if days is not None:
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)
        query = query.gte("date", str(cutoff_date))

    result = query.execute()

    # Get all habits to join with strike data
    habits = supabase.table("habits").select("*").execute()
    habit_map = {h["id"]: h for h in habits.data}

    # Group by habit_id and include habit details
    strikes_by_habit = {}
    for strike in result.data:
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
        "total_strikes": len(result.data),
        "habits_with_strikes": strikes_list,
        "all_strikes": result.data
    }


def get_habit_strikes(habit_id: int) -> List[Dict[str, Any]]:
    """
    Get all strikes for a specific habit

    Args:
        habit_id: The habit ID

    Returns:
        List of strike records
    """
    result = supabase.table("strikes")\
        .select("*")\
        .eq("habit_id", habit_id)\
        .order("created_at", desc=True)\
        .execute()

    return result.data


def get_today_strike_count() -> int:
    """
    Get the total number of strikes logged today (across all habits)

    Returns:
        Total strike count for today
    """
    today = date.today()

    result = supabase.table("strikes")\
        .select("*", count="exact")\
        .eq("date", str(today))\
        .execute()

    return result.count if result.count else 0


def assign_punishment(strike_count: int) -> Dict[str, Any]:
    """
    Assign a punishment habit based on today's total strike count

    Args:
        strike_count: Number of strikes accumulated today

    Returns:
        Dict with punishment details
    """
    import pytz

    # Use Pacific timezone for all time operations
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific_tz)
    today = now_pacific.date()
    current_time = now_pacific.time()

    # Hard-coded punishment escalation rules
    if strike_count == 1:
        punishment_title = "PUNISHMENT: 5K Run"
        start_time = current_time.strftime("%H:%M")
        deadline_time = "23:59"  # End of day
    elif strike_count == 2:
        # CRYPTO PUNISHMENT: Send $10 USDC on Base
        logger.info(f"[PUNISHMENT] Strike 2 triggered - executing crypto punishment")

        if not CRYPTO_ENABLED:
            logger.error("[PUNISHMENT] Crypto module not available!")
            return {
                "status": "error",
                "message": "Strike 2: Crypto punishment not available (module not loaded)",
                "strike_count": strike_count
            }

        # Execute the crypto transfer
        crypto_result = send_usdc_punishment(amount_usd=1.0)  # $1 for testing

        if crypto_result.get("success"):
            logger.info(f"[PUNISHMENT] Crypto punishment successful: {crypto_result.get('tx_hash')}")
            return {
                "status": "crypto_success",
                "message": f"Strike {strike_count}: $10 USDC sent to punishment address",
                "strike_count": strike_count,
                "amount_usd": 10.0,
                "tx_hash": crypto_result.get("tx_hash"),
                "basescan_link": crypto_result.get("basescan_link"),
                "crypto_details": crypto_result
            }
        else:
            logger.error(f"[PUNISHMENT] Crypto punishment failed: {crypto_result.get('error')}")
            return {
                "status": "crypto_error",
                "message": f"Strike {strike_count}: Failed to send USDC - {crypto_result.get('error')}",
                "strike_count": strike_count,
                "error": crypto_result.get("error")
            }
    elif strike_count == 3:
        # Placeholder - just notify
        return {
            "status": "placeholder",
            "message": f"Strike {strike_count} logged. Punishment not yet implemented.",
            "strike_count": strike_count
        }
    else:  # strike_count >= 4
        # Placeholder - just notify
        return {
            "status": "placeholder",
            "message": f"Strike {strike_count} logged. Punishment not yet implemented.",
            "strike_count": strike_count
        }

    # Create the punishment habit
    result = supabase.table("habits").insert({
        "title": punishment_title,
        "start_time": start_time,
        "deadline_time": deadline_time,
        "punishment_habit": True,
        "auto_delete_at": str(today)
    }).execute()

    return {
        "status": "success",
        "message": f"Punishment assigned: {punishment_title}",
        "strike_count": strike_count,
        "punishment": punishment_title,
        "data": result.data
    }
