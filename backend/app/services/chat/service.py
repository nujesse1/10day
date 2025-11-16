"""
Conversation processing logic for the chat LLM
Handles message processing and response generation
"""
import json
from typing import Optional, Dict, Any, List
import logging

from app.core.dependencies import openai_client as client
from app.core.constants import LLM_MODEL_DEFAULT
from app.utils.prompts import SYSTEM_PROMPT, format_baseline_context
from .context import gather_baseline_context, prepare_context_for_media
from .tool_handlers import call_tool
from .tool_schemas import TOOLS

logger = logging.getLogger(__name__)


def _prepare_messages_with_context(
    conversation_history: List[Dict[str, Any]],
    user_input: str,
    baseline_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Prepare messages list with conversation history, new user message, and baseline context

    Args:
        conversation_history: Previous messages in conversation
        user_input: New user message text
        baseline_context: Gathered baseline context data

    Returns:
        List of messages ready for LLM API call
    """
    # Start with conversation history and add new user message
    messages = conversation_history.copy()
    user_message = {"role": "user", "content": user_input}
    messages.append(user_message)

    # Format baseline context using prompts module
    context_summary = format_baseline_context(baseline_context)

    logger.info(f"[PHASE 1] Context gathered: {len(baseline_context['habits'])} habits, {baseline_context['strikes'].get('strike_count', 0)} strikes")

    # Add context as a system message before user message (so LLM sees it)
    messages.insert(-1, {"role": "system", "content": context_summary})

    return messages


def _process_response_output(
    response: Any,
    messages: List[Dict[str, Any]],
    context: Dict[str, Any],
    verbose: bool = False,
    iteration: int = 0
) -> tuple[bool, Optional[str]]:
    """
    Process response output items from the LLM API

    Args:
        response: Response from LLM API
        messages: Current messages list (will be modified)
        context: Tool call context
        verbose: Whether to print debug info
        iteration: Current iteration number

    Returns:
        Tuple of (has_more_function_calls, final_text_content)
        - has_more_function_calls: True if response contains function calls to execute
        - final_text_content: Text response if no more function calls, None otherwise
    """
    has_function_calls = False
    final_text_content = None

    # First pass: check if we have function calls
    for item in response.output:
        if item.type == "message":
            # Extract text content from message
            if hasattr(item, 'content') and item.content:
                final_text_content = item.content[0].text if hasattr(item.content[0], 'text') else None
        elif item.type == "function_call":
            has_function_calls = True

    # If no function calls, return the final text response
    if not has_function_calls:
        if verbose:
            print(f"[Round {iteration}] Model returned final response")
        return False, final_text_content or "I'm not sure how to help with that."

    # We have function calls - process them
    if verbose:
        function_call_count = sum(1 for item in response.output if item.type == "function_call")
        print(f"[Round {iteration}] Model requested {function_call_count} function call(s)")

    # Execute function calls and append results to messages
    for item in response.output:
        if item.type == "function_call":
            # Parse arguments
            function_args = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments

            if verbose:
                print(f"  → Calling {item.name}({json.dumps(function_args)})")

            # Call the tool with context
            function_response = call_tool(item.name, function_args, context)

            if verbose:
                print(f"  ← Result: {function_response}")

            # Append the function call item to messages
            messages.append(item)

            # Append the function result to messages
            messages.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": function_response
            })

    return True, None


def process_user_input(
    user_input: str,
    conversation_history: List[Dict[str, Any]],
    verbose: bool = False,
    media_urls: Optional[List[str]] = None
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Process user input using OpenAI function calling with conversation history

    Args:
        user_input: The user's message
        conversation_history: List of previous messages in the conversation
        verbose: If True, print debug information
        media_urls: Optional list of media URLs (e.g., from WhatsApp/Twilio)

    Returns:
        Tuple of (response_text, updated_conversation_history)
    """
    # Prepare context for tool calls and update user input with media info
    context, additional_text = prepare_context_for_media(media_urls)
    user_input += additional_text

    try:
        # PHASE 1: RESEARCH - Gather baseline context before any response
        logger.info("[PHASE 1] Gathering baseline context...")
        baseline_context = gather_baseline_context()

        # Prepare messages with context
        messages = _prepare_messages_with_context(conversation_history, user_input, baseline_context)

        # Store the original user message for history
        user_message = {"role": "user", "content": user_input}

        # PHASE 2: RESPONSE - Loop to handle multiple rounds of tool calling
        logger.info("[PHASE 2] Beginning response generation...")
        iteration = 0

        while True:
            iteration += 1
            if verbose:
                print(f"[Round {iteration}] Calling model")

            # Use Responses API
            # Extract system prompt if it exists in messages
            system_instructions = None
            input_messages = messages
            if messages and messages[0].get("role") == "system":
                system_instructions = messages[0].get("content")
                input_messages = messages[1:]  # Skip system message in input

            response = client.responses.create(
                model=LLM_MODEL_DEFAULT,
                input=input_messages if input_messages else messages,
                instructions=system_instructions,
                tools=TOOLS
            )

            # Process response output
            has_more_calls, final_content = _process_response_output(
                response, messages, context, verbose, iteration
            )

            # If no more function calls, we have our final response
            if not has_more_calls:
                # Update conversation history with user message and final assistant response
                conversation_history.append(user_message)
                conversation_history.append({"role": "assistant", "content": final_content})
                return final_content, conversation_history

    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        conversation_history.append(user_message)
        conversation_history.append({"role": "assistant", "content": error_msg})
        return error_msg, conversation_history


def create_new_conversation() -> List[Dict[str, Any]]:
    """Create a new conversation with system prompt initialized"""
    return [{"role": "system", "content": SYSTEM_PROMPT}]
