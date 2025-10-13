"""
Chat Engine - Core LLM processing logic for habit tracking
Shared between CLI and WhatsApp interfaces
"""
import json
import os
from typing import Optional, Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT
import habit_service
from proof_verifier import verify_proof, analyze_image_for_habit
import logging

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger(__name__)

# Define tools that the LLM can call
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_habits",
            "description": "Get the list of all current habits from the backend",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_habit",
            "description": "Add a new habit to track",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The name/title of the habit to add"
                    }
                },
                "required": ["title"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_habit",
            "description": "Remove/delete an existing habit",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The name/title of the habit to remove"
                    }
                },
                "required": ["title"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_habit",
            "description": "Mark a habit as completed for today. REQUIRES visual proof - user must provide a screenshot or photo as evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The name/title of the habit to mark complete"
                    },
                    "proof_provided": {
                        "type": "boolean",
                        "description": "Whether the user provided proof (image/screenshot) with their message"
                    }
                },
                "required": ["title", "proof_provided"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_status",
            "description": "Show today's habit completion status",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_habit_from_image",
            "description": "Intelligently analyze an image, identify which habit it proves, match to existing habits, and mark complete. Use this when user sends an image without specifying which habit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "Any text the user included with the image (e.g., 'done', 'completed', or empty)"
                    }
                },
                "required": ["user_message"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
]

# Tool implementation functions - these call the habit service directly
def tool_get_current_habits() -> str:
    """Get list of all current habits"""
    try:
        data = habit_service.get_today_habits()
        habits = data.get("habits", [])
        habit_titles = [h["title"] for h in habits]
        return json.dumps({"habits": habit_titles})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_add_habit(title: str) -> str:
    """Add a new habit"""
    try:
        result = habit_service.add_habit(title)
        return json.dumps({"success": True, "message": f"Added habit '{title}'"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def tool_remove_habit(title: str) -> str:
    """Remove a habit"""
    try:
        result = habit_service.remove_habit_by_title(title)
        return json.dumps({"success": True, "message": result.get("message", f"Removed habit '{title}'")})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def tool_complete_habit(title: str, proof_provided: bool, proof_source: Optional[str] = None, is_twilio_url: bool = False) -> str:
    """
    Mark a habit as complete - REQUIRES proof verification

    Args:
        title: Habit title
        proof_provided: Whether user provided proof
        proof_source: Twilio media URL or local file path (injected by process_user_input)
        is_twilio_url: Whether proof_source is a Twilio URL
    """
    try:
        # DEMAND PROOF - No proof, no completion
        if not proof_provided or not proof_source:
            return json.dumps({
                "success": False,
                "error": "PROOF REQUIRED. You must provide a screenshot or photo as evidence. No excuses."
            })

        logger.info(f"Verifying proof for habit: {title}")

        # Verify the proof using GPT-4 Vision
        verification = verify_proof(
            image_source=proof_source,
            habit_title=title,
            is_twilio_url=is_twilio_url
        )

        # Check verification result
        if not verification.verified:
            return json.dumps({
                "success": False,
                "error": f"PROOF REJECTED. {verification.reasoning}",
                "confidence": verification.confidence
            })

        logger.info(f"Proof verified with {verification.confidence} confidence: {verification.reasoning}")

        # Proof verified - complete the habit
        result = habit_service.complete_habit_by_title(title, proof_source)

        return json.dumps({
            "success": True,
            "message": f"Completed habit '{result.get('habit', title)}' - proof verified",
            "verification": {
                "confidence": verification.confidence,
                "reasoning": verification.reasoning
            }
        })
    except Exception as e:
        logger.error(f"Error completing habit with proof: {e}")
        return json.dumps({"success": False, "error": str(e)})


def tool_show_status() -> str:
    """Show today's status"""
    try:
        data = habit_service.get_today_habits()

        habits = data.get("habits", [])
        date_str = data.get("date", "today")

        completed_count = sum(1 for h in habits if h["completed"])
        total = len(habits)

        return json.dumps({
            "date": date_str,
            "habits": habits,
            "completed": completed_count,
            "total": total
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_complete_habit_from_image(user_message: str, proof_source: Optional[str] = None, is_twilio_url: bool = False) -> str:
    """
    Smart image-based habit completion:
    1. Analyze image to identify what habit it proves
    2. Match to existing habits using LLM
    3. Verify proof is legitimate
    4. Mark complete if all checks pass

    Args:
        user_message: Any text the user included
        proof_source: Image URL or file path (injected by process_user_input)
        is_twilio_url: Whether proof_source is a Twilio URL
    """
    try:
        # Step 1: Check if image was provided
        if not proof_source:
            return json.dumps({
                "success": False,
                "error": "No image provided. Cannot complete habit without proof."
            })

        logger.info(f"[SMART COMPLETION] Starting smart image-based completion")
        logger.info(f"[SMART COMPLETION] User message: {user_message}")

        # Step 2: Analyze the image to identify what habit it represents
        logger.info(f"[SMART COMPLETION] Step 1: Analyzing image to identify habit...")
        analysis = analyze_image_for_habit(
            image_source=proof_source,
            is_twilio_url=is_twilio_url
        )

        logger.info(f"[SMART COMPLETION] Identified: {analysis.habit_identified}")
        logger.info(f"[SMART COMPLETION] Activity type: {analysis.activity_type}")
        logger.info(f"[SMART COMPLETION] Details: {analysis.key_details}")

        # Step 3: Get existing habits and match using LLM
        logger.info(f"[SMART COMPLETION] Step 2: Matching to existing habits...")
        habits_data = habit_service.get_today_habits()
        existing_habits = habits_data.get("habits", [])

        if not existing_habits:
            return json.dumps({
                "success": False,
                "error": "No habits found to match against. Add some habits first."
            })

        # Use LLM to find best matching habit
        matched_habit = habit_service.find_habit_by_llm(
            analysis.habit_identified,
            existing_habits
        )

        if not matched_habit:
            return json.dumps({
                "success": False,
                "error": f"Could not match '{analysis.habit_identified}' to any existing habit. Available habits: {', '.join([h['title'] for h in existing_habits])}",
                "identified_habit": analysis.habit_identified,
                "confidence": analysis.confidence
            })

        logger.info(f"[SMART COMPLETION] Matched to habit: {matched_habit['title']}")

        # Step 4: Verify the proof is legitimate for this habit
        logger.info(f"[SMART COMPLETION] Step 3: Verifying proof legitimacy...")
        verification = verify_proof(
            image_source=proof_source,
            habit_title=matched_habit['title'],
            is_twilio_url=is_twilio_url,
            additional_context=f"Image shows: {analysis.key_details}"
        )

        if not verification.verified:
            return json.dumps({
                "success": False,
                "error": f"PROOF REJECTED for habit '{matched_habit['title']}'. {verification.reasoning}",
                "identified_habit": analysis.habit_identified,
                "matched_habit": matched_habit['title'],
                "confidence": verification.confidence
            })

        logger.info(f"[SMART COMPLETION] Proof verified: {verification.reasoning}")

        # Step 5: Mark the habit complete
        logger.info(f"[SMART COMPLETION] Step 4: Marking habit complete...")
        result = habit_service.complete_habit_by_title(matched_habit['title'], proof_source)

        return json.dumps({
            "success": True,
            "message": f"Completed habit '{matched_habit['title']}' based on image analysis",
            "analysis": {
                "identified": analysis.habit_identified,
                "matched_to": matched_habit['title'],
                "details": analysis.key_details,
                "analysis_confidence": analysis.confidence
            },
            "verification": {
                "verified": verification.verified,
                "confidence": verification.confidence,
                "reasoning": verification.reasoning
            }
        })

    except Exception as e:
        logger.error(f"[SMART COMPLETION] Error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)})


def call_tool(name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    """
    Route tool calls to appropriate functions

    Args:
        name: Tool function name
        arguments: Tool arguments from LLM
        context: Additional context (e.g., media URLs from WhatsApp)
    """
    if name == "get_current_habits":
        return tool_get_current_habits()
    elif name == "add_habit":
        return tool_add_habit(**arguments)
    elif name == "remove_habit":
        return tool_remove_habit(**arguments)
    elif name == "complete_habit":
        # Inject proof source from context if available
        if context and "proof_source" in context:
            arguments["proof_source"] = context["proof_source"]
            arguments["is_twilio_url"] = context.get("is_twilio_url", False)
        return tool_complete_habit(**arguments)
    elif name == "complete_habit_from_image":
        # Inject proof source from context if available
        if context and "proof_source" in context:
            arguments["proof_source"] = context["proof_source"]
            arguments["is_twilio_url"] = context.get("is_twilio_url", False)
        return tool_complete_habit_from_image(**arguments)
    elif name == "show_status":
        return tool_show_status()
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


def process_user_input(
    user_input: str,
    conversation_history: List[Dict[str, Any]],
    verbose: bool = False,
    media_urls: Optional[List[str]] = None
) -> tuple[str, List[Dict[str, Any]]]:
    """Process user input using OpenAI function calling with conversation history

    Args:
        user_input: The user's message
        conversation_history: List of previous messages in the conversation
        verbose: If True, print debug information
        media_urls: Optional list of media URLs (e.g., from WhatsApp/Twilio)

    Returns:
        Tuple of (response_text, updated_conversation_history)
    """
    # Prepare context for tool calls
    context = {}
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
        user_input += f"\n[User attached {len(media_urls)} image(s) as proof]"

    # Start with conversation history and add new user message
    messages = conversation_history.copy()
    user_message = {"role": "user", "content": user_input}
    messages.append(user_message)

    try:
        # Loop to handle multiple rounds of tool calling
        iteration = 0

        while True:
            iteration += 1
            if verbose:
                print(f"[Round {iteration}] Calling model")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # If no tool calls, we have a final text response
            if not tool_calls:
                final_content = response_message.content or "I'm not sure how to help with that."
                if verbose:
                    print(f"[Round {iteration}] Model returned final response")

                # Update conversation history with user message and final assistant response
                conversation_history.append(user_message)
                conversation_history.append({"role": "assistant", "content": final_content})

                return final_content, conversation_history

            # Model wants to call tools
            if verbose:
                print(f"[Round {iteration}] Model requested {len(tool_calls)} tool call(s)")

            # Add assistant's response to messages
            messages.append(response_message)

            # Execute all tool calls
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                if verbose:
                    print(f"  → Calling {function_name}({json.dumps(function_args)})")

                # Call the tool with context
                function_response = call_tool(function_name, function_args, context)

                if verbose:
                    print(f"  ← Result: {function_response}")

                # Add tool response to messages
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response
                })

    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        conversation_history.append(user_message)
        conversation_history.append({"role": "assistant", "content": error_msg})
        return error_msg, conversation_history


def create_new_conversation() -> List[Dict[str, Any]]:
    """Create a new conversation with system prompt initialized"""
    return [{"role": "system", "content": SYSTEM_PROMPT}]
