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

# Start the scheduler on app startup
@app.on_event("startup")
async def startup_event():
    """Start background scheduler when FastAPI starts"""
    try:
        from scheduler import start_scheduler
        start_scheduler()
        print("✓ Habit reminder scheduler started")
    except ImportError as e:
        print(f"Warning: Could not import scheduler: {e}")
    except Exception as e:
        print(f"Warning: Could not start scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background scheduler when FastAPI shuts down"""
    try:
        from scheduler import stop_scheduler
        stop_scheduler()
        print("✓ Habit reminder scheduler stopped")
    except Exception as e:
        print(f"Warning: Error stopping scheduler: {e}")

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Request models
class AddHabitRequest(BaseModel):
    title: str
    start_time: str
    deadline_time: str


class RemoveHabitRequest(BaseModel):
    title: str


class CompleteHabitRequest(BaseModel):
    title: str
    proof_path: Optional[str] = None


class SetScheduleRequest(BaseModel):
    title: str
    start_time: Optional[str] = None
    deadline_time: Optional[str] = None


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Server is alive"}


@app.post("/add-habit")
async def add_habit(request: AddHabitRequest):
    """Add a new habit with required schedule times"""
    try:
        return habit_service.add_habit(request.title, request.start_time, request.deadline_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


@app.post("/habits/schedule")
async def set_habit_schedule(request: SetScheduleRequest):
    """Set reminder schedule for a habit"""
    try:
        return habit_service.set_habit_schedule(
            request.title,
            request.start_time,
            request.deadline_time
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
