"""
Habit Service - Core business logic for habit management
Shared between FastAPI endpoints and chat engine to avoid HTTP deadlock
"""
from datetime import date
from typing import Optional, Dict, Any
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

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


def add_habit(title: str) -> Dict[str, Any]:
    """Add a new habit"""
    result = supabase.table("habits").insert({
        "title": title
    }).execute()

    return {
        "status": "success",
        "message": f"Habit '{title}' added successfully",
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
            "completion_id": completion["id"] if completion else None
        })

    return {
        "status": "success",
        "date": str(today),
        "habits": result
    }
