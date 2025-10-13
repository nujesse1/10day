"""
Session Store - Manages per-user conversation histories for WhatsApp
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
from chat_engine import create_new_conversation

# In-memory session storage
# Format: {phone_number: {"history": [...], "last_active": datetime}}
sessions: Dict[str, Dict[str, Any]] = {}

# Session timeout in minutes
SESSION_TIMEOUT_MINUTES = 30


def get_or_create_session(phone_number: str) -> List[Dict[str, Any]]:
    """
    Get conversation history for a user, or create a new one if it doesn't exist

    Args:
        phone_number: User's phone number (e.g., "whatsapp:+13128856151")

    Returns:
        List of conversation messages
    """
    # Clean up old sessions first
    cleanup_expired_sessions()

    # Check if session exists
    if phone_number not in sessions:
        # Create new session with system prompt
        sessions[phone_number] = {
            "history": create_new_conversation(),
            "last_active": datetime.now()
        }

    # Update last active time
    sessions[phone_number]["last_active"] = datetime.now()

    return sessions[phone_number]["history"]


def update_session(phone_number: str, history: List[Dict[str, Any]]) -> None:
    """
    Update conversation history for a user

    Args:
        phone_number: User's phone number
        history: Updated conversation history
    """
    sessions[phone_number] = {
        "history": history,
        "last_active": datetime.now()
    }


def cleanup_expired_sessions() -> int:
    """
    Remove sessions that have been inactive for longer than SESSION_TIMEOUT_MINUTES

    Returns:
        Number of sessions removed
    """
    cutoff_time = datetime.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    expired_numbers = [
        phone_number
        for phone_number, session_data in sessions.items()
        if session_data["last_active"] < cutoff_time
    ]

    for phone_number in expired_numbers:
        del sessions[phone_number]

    return len(expired_numbers)


def get_active_session_count() -> int:
    """
    Get the number of currently active sessions

    Returns:
        Number of active sessions
    """
    return len(sessions)


def clear_session(phone_number: str) -> bool:
    """
    Manually clear a user's session

    Args:
        phone_number: User's phone number

    Returns:
        True if session existed and was cleared, False otherwise
    """
    if phone_number in sessions:
        del sessions[phone_number]
        return True
    return False


def get_session_info(phone_number: str) -> Dict[str, Any]:
    """
    Get information about a user's session

    Args:
        phone_number: User's phone number

    Returns:
        Dictionary with session info, or None if session doesn't exist
    """
    if phone_number not in sessions:
        return None

    session = sessions[phone_number]
    return {
        "phone_number": phone_number,
        "message_count": len(session["history"]),
        "last_active": session["last_active"].isoformat(),
        "age_minutes": (datetime.now() - session["last_active"]).total_seconds() / 60
    }
