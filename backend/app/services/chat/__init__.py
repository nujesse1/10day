"""
Chat service module - LLM conversation processing
Exports the main public interface for chat functionality
"""
from .service import process_user_input, create_new_conversation
from .context import gather_baseline_context, prepare_context_for_media
from .tool_schemas import TOOLS
from .tool_handlers import call_tool

__all__ = [
    # Conversation management
    'process_user_input',
    'create_new_conversation',

    # Context gathering
    'gather_baseline_context',
    'prepare_context_for_media',

    # Tools
    'TOOLS',
    'call_tool'
]
