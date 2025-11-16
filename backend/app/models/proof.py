"""
Pydantic models for proof verification
"""
from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence levels for proof verification"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProofVerification(BaseModel):
    """Structured output model for proof verification"""
    verified: bool = Field(..., description="Whether the proof was verified")
    confidence: ConfidenceLevel = Field(..., description="Confidence level of verification")
    reasoning: str = Field(..., description="Explanation of verification decision")


class ImageAnalysis(BaseModel):
    """Structured output for analyzing what habit(s) an image represents"""
    matched_habit_titles: List[str] = Field(..., description="List of ALL exact habit titles from the provided list that are proven by this image")
    habit_identified: str = Field(..., description="Natural language description of ALL activities/habits shown in the image")
    activity_type: str = Field(..., description="Primary activity type (e.g., exercise, meditation, reading, nutrition)")
    key_details: str = Field(..., description="ALL specific details visible in the image, including all numerical data (distances, durations, dates, etc.)")
    confidence: ConfidenceLevel = Field(..., description="Confidence level of analysis")
    multiple_habits_detected: bool = Field(..., description="True if image proves multiple habits, False if only one")
