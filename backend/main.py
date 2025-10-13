from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import date
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel
import os
import json
import habit_service

# Load environment variables
load_dotenv()

app = FastAPI(title="Drill Sergeant API", version="0.1.0")

# Import and include WhatsApp router
try:
    from whatsapp import router as whatsapp_router
    app.include_router(whatsapp_router)
except ImportError as e:
    print(f"Warning: Could not import WhatsApp router: {e}")
except Exception as e:
    print(f"Warning: Could not initialize WhatsApp integration: {e}")

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Request models
class AddHabitRequest(BaseModel):
    title: str


class RemoveHabitRequest(BaseModel):
    title: str


class CompleteHabitRequest(BaseModel):
    title: str
    proof_path: Optional[str] = None


# Helper function: LLM-based habit matching
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


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Server is alive"}


@app.post("/add-habit")
async def add_habit(request: AddHabitRequest):
    """Add a new habit"""
    try:
        return habit_service.add_habit(request.title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/remove-habit/{habit_id}")
async def remove_habit_by_id(habit_id: int):
    """Remove a habit by ID (legacy endpoint)"""
    try:
        # Delete the habit
        result = supabase.table("habits").delete().eq("id", habit_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Habit not found")

        return {
            "status": "success",
            "message": f"Habit {habit_id} removed successfully",
            "data": result.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/remove-habit")
async def remove_habit(request: RemoveHabitRequest):
    """Remove a habit by title (with LLM matching)"""
    try:
        return habit_service.remove_habit_by_title(request.title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/habits/generate-daily")
async def generate_daily_completions():
    """Generate completion entries for all habits for today"""
    try:
        today = date.today()

        # Get all active habits
        habits_result = supabase.table("habits").select("id").execute()

        if not habits_result.data:
            return {
                "status": "success",
                "message": "No habits found",
                "data": []
            }

        # Check if completions already exist for today
        existing = supabase.table("habit_completions")\
            .select("habit_id")\
            .eq("date", str(today))\
            .execute()

        existing_habit_ids = {item["habit_id"] for item in existing.data}

        # Create completions for habits that don't have one today
        completions_to_create = []
        for habit in habits_result.data:
            if habit["id"] not in existing_habit_ids:
                completions_to_create.append({
                    "habit_id": habit["id"],
                    "date": str(today),
                    "completed": False
                })

        if completions_to_create:
            result = supabase.table("habit_completions").insert(completions_to_create).execute()
            return {
                "status": "success",
                "message": f"Created {len(completions_to_create)} completion entries for today",
                "data": result.data
            }
        else:
            return {
                "status": "success",
                "message": "All habits already have completion entries for today",
                "data": []
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/habits/{habit_id}/complete")
async def mark_habit_complete_by_id(habit_id: int, proof_path: Optional[str] = None):
    """Mark a habit as complete for today by ID (legacy endpoint)"""
    try:
        today = date.today()

        # Check if completion entry exists for today
        existing = supabase.table("habit_completions")\
            .select("*")\
            .eq("habit_id", habit_id)\
            .eq("date", str(today))\
            .execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="No completion entry found for this habit today. Run /habits/generate-daily first.")

        # Update the completion
        update_data = {"completed": True}
        if proof_path:
            update_data["proof_path"] = proof_path

        result = supabase.table("habit_completions")\
            .update(update_data)\
            .eq("habit_id", habit_id)\
            .eq("date", str(today))\
            .execute()

        # Get habit title
        habit = supabase.table("habits").select("title").eq("id", habit_id).execute()
        habit_title = habit.data[0]["title"] if habit.data else "Unknown"

        return {
            "status": "success",
            "habit": habit_title,
            "completed": True,
            "proof": proof_path,
            "data": result.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/complete-habit")
async def complete_habit(request: CompleteHabitRequest):
    """Mark a habit as complete for today by title (with LLM matching)"""
    try:
        return habit_service.complete_habit_by_title(request.title, request.proof_path)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/habits/today")
async def get_today_habits():
    """Get all habits with today's completion status"""
    try:
        return habit_service.get_today_habits()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summary/today")
async def get_daily_summary():
    """Get today's summary of habit completion"""
    try:
        today = date.today()

        # Get all habits
        habits = supabase.table("habits").select("id, title").execute()
        total_habits = len(habits.data)

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
        completions = supabase.table("habit_completions")\
            .select("*")\
            .eq("date", str(today))\
            .execute()

        completion_map = {c["habit_id"]: c for c in completions.data}

        completed_count = sum(1 for c in completions.data if c["completed"])
        missed_habits = []
        completed_habits = []

        for habit in habits.data:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
