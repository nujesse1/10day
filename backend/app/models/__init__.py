"""
Pydantic models for the application
"""
from app.models.habit import (
    AddHabitRequest,
    RemoveHabitRequest,
    CompleteHabitRequest,
    SetScheduleRequest
)
from app.models.proof import ProofVerification, ImageAnalysis
from app.models.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    NewConversationResponse
)

__all__ = [
    "AddHabitRequest",
    "RemoveHabitRequest",
    "CompleteHabitRequest",
    "SetScheduleRequest",
    "ProofVerification",
    "ImageAnalysis",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "NewConversationResponse"
]
