"""
Pydantic models for habits
"""
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class AddHabitRequest(BaseModel):
    """Request model for adding a new habit"""
    title: str = Field(..., min_length=1, max_length=200, description="Habit title")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    deadline_time: str = Field(..., description="Deadline time in HH:MM format (24-hour)")

    @field_validator('start_time', 'deadline_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time format is HH:MM"""
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError(f"Invalid time format '{v}'. Use HH:MM (24-hour format)")


class RemoveHabitRequest(BaseModel):
    """Request model for removing a habit"""
    title: str = Field(..., min_length=1, description="Habit title or description to match")


class CompleteHabitRequest(BaseModel):
    """Request model for completing a habit"""
    title: str = Field(..., min_length=1, description="Habit title or description to match")
    proof_path: Optional[str] = Field(None, description="Optional path to proof file")


class SetScheduleRequest(BaseModel):
    """Request model for setting habit schedule"""
    title: str = Field(..., min_length=1, description="Habit title or description to match")
    start_time: Optional[str] = Field(None, description="Start time in HH:MM format (24-hour)")
    deadline_time: Optional[str] = Field(None, description="Deadline time in HH:MM format (24-hour)")

    @field_validator('start_time', 'deadline_time')
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format is HH:MM if provided"""
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError(f"Invalid time format '{v}'. Use HH:MM (24-hour format)")
