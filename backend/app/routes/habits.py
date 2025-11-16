"""
Habit Routes - Endpoints for habit management
"""
from fastapi import APIRouter, HTTPException
from app.models.habit import (
    AddHabitRequest,
    RemoveHabitRequest,
    CompleteHabitRequest,
    SetScheduleRequest
)
from app.services import habit_service
from app.core.exceptions import (
    HabitNotFoundError,
    InvalidHabitDataError,
    DatabaseError,
    ExternalServiceError
)

router = APIRouter(prefix="/habits", tags=["habits"])


@router.post("")
async def add_habit(request: AddHabitRequest):
    """Add a new habit with required schedule times"""
    try:
        return habit_service.add_habit(request.title, request.start_time, request.deadline_time)
    except InvalidHabitDataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/remove")
async def remove_habit(request: RemoveHabitRequest):
    """Remove a habit by title (with LLM matching)"""
    try:
        return habit_service.remove_habit_by_title(request.title)
    except HabitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (DatabaseError, ExternalServiceError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/complete")
async def complete_habit(request: CompleteHabitRequest):
    """Mark a habit as complete for today by title (with LLM matching)"""
    try:
        return habit_service.complete_habit_by_title(request.title, request.proof_path)
    except HabitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (DatabaseError, ExternalServiceError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/today")
async def get_today_habits():
    """Get all habits with today's completion status"""
    try:
        return habit_service.get_today_habits()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/today")
async def get_daily_summary():
    """Get today's summary of habit completion"""
    try:
        return habit_service.get_daily_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule")
async def set_habit_schedule(request: SetScheduleRequest):
    """Set reminder schedule for a habit"""
    try:
        return habit_service.set_habit_schedule(
            request.title,
            request.start_time,
            request.deadline_time
        )
    except HabitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidHabitDataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (DatabaseError, ExternalServiceError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
