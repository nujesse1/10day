#!/usr/bin/env python3
"""
Drill Sergeant CLI - Natural language habit tracker using OpenAI function calling
"""
import json
import os
import requests
from typing import Optional, Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Backend API base URL
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

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
            "description": "Mark a habit as completed for today",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The name/title of the habit to mark complete"
                    },
                    "proof_path": {
                        "type": ["string", "null"],
                        "description": "Optional file path to proof/evidence of completion"
                    }
                },
                "required": ["title", "proof_path"],
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
    }
]

# Tool implementation functions - these call the backend API
def tool_get_current_habits() -> str:
    """Get list of all current habits"""
    try:
        response = requests.get(f"{API_BASE}/habits/today")
        response.raise_for_status()
        data = response.json()
        habits = data.get("habits", [])
        habit_titles = [h["title"] for h in habits]
        return json.dumps({"habits": habit_titles})
    except Exception as e:
        return json.dumps({"error": str(e)})
def tool_add_habit(title: str) -> str:
    """Add a new habit"""
    try:
        response = requests.post(f"{API_BASE}/add-habit", json={"title": title})
        response.raise_for_status()
        data = response.json()
        return json.dumps({"success": True, "message": f"Added habit '{title}'"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def tool_remove_habit(title: str) -> str:
    """Remove a habit"""
    try:
        response = requests.post(f"{API_BASE}/remove-habit", json={"title": title})
        response.raise_for_status()
        data = response.json()
        return json.dumps({"success": True, "message": data.get("message", f"Removed habit '{title}'")})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def tool_complete_habit(title: str, proof_path: Optional[str] = None) -> str:
    """Mark a habit as complete"""
    try:
        payload = {"title": title}
        if proof_path:
            payload["proof_path"] = proof_path

        response = requests.post(f"{API_BASE}/complete-habit", json=payload)
        response.raise_for_status()
        data = response.json()

        msg = f"Completed habit '{data.get('habit', title)}'"
        if proof_path:
            msg += f" with proof: {proof_path}"
        return json.dumps({"success": True, "message": msg})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def tool_show_status() -> str:
    """Show today's status"""
    try:
        response = requests.get(f"{API_BASE}/habits/today")
        response.raise_for_status()
        data = response.json()

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


def call_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Route tool calls to appropriate functions"""
    if name == "get_current_habits":
        return tool_get_current_habits()
    elif name == "add_habit":
        return tool_add_habit(**arguments)
    elif name == "remove_habit":
        return tool_remove_habit(**arguments)
    elif name == "complete_habit":
        return tool_complete_habit(**arguments)
    elif name == "show_status":
        return tool_show_status()
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


def process_user_input(user_input: str, conversation_history: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    """Process user input using OpenAI function calling with conversation history

    Args:
        user_input: The user's message
        conversation_history: List of previous messages in the conversation

    Returns:
        Tuple of (response_text, updated_conversation_history)
    """
    # Start with conversation history and add new user message
    messages = conversation_history.copy()
    user_message = {"role": "user", "content": user_input}
    messages.append(user_message)

    try:
        # Loop to handle multiple rounds of tool calling
        iteration = 0

        while True:
            iteration += 1
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
                print(f"[Round {iteration}] Model returned final response")

                # Update conversation history with user message and final assistant response
                conversation_history.append(user_message)
                conversation_history.append({"role": "assistant", "content": final_content})

                return final_content, conversation_history

            # Model wants to call tools
            print(f"[Round {iteration}] Model requested {len(tool_calls)} tool call(s)")

            # Add assistant's response to messages
            messages.append(response_message)

            # Execute all tool calls
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                print(f"  → Calling {function_name}({json.dumps(function_args)})")

                # Call the tool
                function_response = call_tool(function_name, function_args)

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


def main():
    """Main CLI loop"""
    print("🎖️  Drill Sergeant CLI v0")
    print("Natural language habit tracker")
    print(f"Connected to: {API_BASE}")
    print("Type 'quit' or 'exit' to leave\n")

    # Initialize conversation history with system prompt
    conversation_history = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("🎖️  Dismissed!")
                break

            # Process input with tool calling and conversation history
            result, conversation_history = process_user_input(user_input, conversation_history)
            print(result)
            print()

        except KeyboardInterrupt:
            print("\n🎖️  Dismissed!")
            break
        except EOFError:
            print("\n🎖️  Dismissed!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}\n")


if __name__ == "__main__":
    main()
