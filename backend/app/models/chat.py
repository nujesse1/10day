"""
Chat Models - Request/Response schemas for chat endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatMessage(BaseModel):
    """Single message in a conversation"""
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request to process a chat message"""
    message: str = Field(..., description="User message to process")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional conversation history. If not provided, a new conversation is created."
    )
    media_urls: Optional[List[str]] = Field(
        default=None,
        description="Optional list of media URLs for proof verification"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose debug output"
    )


class ChatResponse(BaseModel):
    """Response from chat processing"""
    response: str = Field(..., description="Assistant's response text")
    conversation_history: List[Dict[str, Any]] = Field(
        ...,
        description="Updated conversation history including new messages"
    )


class NewConversationResponse(BaseModel):
    """Response for new conversation creation"""
    conversation_history: List[Dict[str, Any]] = Field(
        ...,
        description="New conversation history with system prompt"
    )
    message: str = Field(
        default="New conversation created",
        description="Status message"
    )
