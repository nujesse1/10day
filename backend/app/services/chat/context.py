"""
Context gathering for chat conversations
Handles collecting baseline context before LLM interactions
"""
import json
from typing import Optional, Dict, Any, List
import logging

from app.services.habits import get_today_habits
from .tool_handlers import tool_get_current_time, tool_get_strikes

logger = logging.getLogger(__name__)


def gather_baseline_context() -> Dict[str, Any]:
    """
    Automatically gather baseline context before any LLM interaction.
    This ensures the LLM always has fresh, accurate data to work with.

    Returns:
        Dict with current_time, habits, and strikes
    """
    try:
        # Get current time
        time_result = tool_get_current_time()
        time_data = json.loads(time_result)

        # Get today's habits with completion status
        habits_data = get_today_habits()

        # Get recent strikes (last 7 days)
        strikes_result = tool_get_strikes(habit_id=None, days=7)
        strikes_data = json.loads(strikes_result)

        return {
            "current_time": time_data,
            "habits": habits_data.get("habits", []),
            "strikes": strikes_data
        }
    except Exception as e:
        logger.error(f"Error gathering baseline context: {e}")
        return {
            "current_time": {},
            "habits": [],
            "strikes": {},
            "error": str(e)
        }


def prepare_context_for_media(media_urls: Optional[List[str]]) -> tuple[Dict[str, Any], str]:
    """
    Prepare context dictionary and additional user message text for media attachments

    Args:
        media_urls: Optional list of media URLs/paths

    Returns:
        Tuple of (context dict, additional_message_text)
    """
    context = {}
    additional_text = ""

    if media_urls and len(media_urls) > 0:
        # Use the first media URL/path as proof source
        proof_source = media_urls[0]
        context["proof_source"] = proof_source

        # Auto-detect if it's a Twilio URL or local file path
        is_twilio_url = proof_source.startswith("http://") or proof_source.startswith("https://")
        context["is_twilio_url"] = is_twilio_url

        logger.info(f"Processing with proof: {proof_source}")
        logger.info(f"Proof type: {'Twilio URL' if is_twilio_url else 'Local file'}")

        # Append media info to user message for LLM context
        additional_text = f"\n[User attached {len(media_urls)} image(s) as proof]"

    return context, additional_text
