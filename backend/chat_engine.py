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
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger(__name__)

# Define tools that the LLM can call (Responses API format)
TOOLS = [
    # COMMENTED OUT: Use query_database instead
    # {
    #     "type": "function",
    #     "name": "get_current_habits",
    #     "description": "Get the list of all current habits from the backend",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {},
    #         "required": [],
    #         "additionalProperties": False
    #     }
    # },
    {
        "type": "function",
        "name": "add_habit",
        "description": "Add a new habit to track. MUST include start time (when to begin) and deadline time (when it must be completed by).",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The name/title of the habit to add"
                },
                "start_time": {
                    "type": "string",
                    "description": "Time when habit should be started in HH:MM format (24-hour), e.g., '07:00' for 7am"
                },
                "deadline_time": {
                    "type": "string",
                    "description": "Time when habit must be completed by in HH:MM format (24-hour), e.g., '20:00' for 8pm"
                }
            },
            "required": ["title", "start_time", "deadline_time"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
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
        }
    },
    {
        "type": "function",
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
        }
    },
    # COMMENTED OUT: Use query_database instead
    # {
    #     "type": "function",
    #     "name": "show_status",
    #     "description": "Show today's habit completion status",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {},
    #         "required": [],
    #         "additionalProperties": False
    #     }
    # },
    {
        "type": "function",
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
        }
    },
    {
        "type": "function",
        "name": "set_habit_schedule",
        "description": "Set reminder schedule for a habit. Specify when to send start reminder and/or deadline reminder.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The name/title of the habit to schedule"
                },
                "start_time": {
                    "type": ["string", "null"],
                    "description": "Time to send start reminder in HH:MM format (24-hour), e.g., '07:00' for 7am. Set to null to clear."
                },
                "deadline_time": {
                    "type": ["string", "null"],
                    "description": "Time to send deadline reminder in HH:MM format (24-hour), e.g., '20:00' for 8pm. Set to null to clear."
                }
            },
            "required": ["title", "start_time", "deadline_time"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_current_time",
        "description": "Get the current date and time with timezone information. Use this to answer questions about the current time or to calculate time remaining for habits.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_strikes",
        "description": "Get strike count and history. Use this when user asks about strikes, violations, or how many times they've failed.",
        "parameters": {
            "type": "object",
            "properties": {
                "habit_id": {
                    "type": ["integer", "null"],
                    "description": "Optional habit ID to get strikes for specific habit. If null, returns all strikes."
                },
                "days": {
                    "type": ["integer", "null"],
                    "description": "Optional number of days to look back. If null, returns all time."
                }
            },
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_database_schema",
        "description": "PREFERRED TOOL: Get the complete database schema showing all tables, columns, types, and relationships. Use this FIRST when user asks about habits, deadlines, status, or any data. Returns dynamically discovered schema with sample values.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "query_database",
        "description": "PREFERRED TOOL: Execute any SELECT query to retrieve data from the database. Use this to get habits, deadlines, completion status, or any other information. Always use get_database_schema first to understand available tables and columns. Example: 'SELECT title, deadline_time FROM habits'",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The SELECT SQL query to execute. Must be a read-only SELECT statement. Can select any columns from any table discovered in the schema."
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
    {"type": "web_search"}
]

# Tool implementation functions - these call the habit service directly
def tool_add_habit(title: str, start_time: str, deadline_time: str) -> str:
    """Add a new habit with required schedule times"""
    try:
        result = habit_service.add_habit(title, start_time, deadline_time)
        return json.dumps({
            "success": True,
            "message": result.get("message"),
            "start_time": start_time,
            "deadline_time": deadline_time
        })
    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"Error adding habit: {e}")
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


def tool_set_habit_schedule(title: str, start_time: Optional[str] = None, deadline_time: Optional[str] = None) -> str:
    """Set schedule for a habit"""
    try:
        result = habit_service.set_habit_schedule(title, start_time, deadline_time)
        return json.dumps({
            "success": True,
            "message": result.get("message"),
            "habit": result.get("habit"),
            "start_time": result.get("start_time"),
            "deadline_time": result.get("deadline_time")
        })
    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"Error setting habit schedule: {e}")
        return json.dumps({"success": False, "error": str(e)})


def tool_get_current_time() -> str:
    """Get the current date and time"""
    try:
        # Always use Pacific timezone
        local_tz = pytz.timezone('America/Los_Angeles')
        now = datetime.now(local_tz)
        tz_name = now.strftime('%Z')

        return json.dumps({
            "success": True,
            "current_time": now.strftime("%H:%M:%S"),
            "current_date": now.strftime("%Y-%m-%d"),
            "day_of_week": now.strftime("%A"),
            "timezone": tz_name,
            "iso_format": now.isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting current time: {e}")
        return json.dumps({"success": False, "error": str(e)})


def tool_get_database_schema() -> str:
    """
    Get the complete database schema including tables, columns, types, and relationships
    Dynamically discovers schema from the database
    """
    try:
        # Get all table names by trying to query each known table's structure
        tables = {}

        # Known possible tables - discover what actually exists
        possible_tables = ['habits', 'habit_completions', 'reminder_log']

        for table_name in possible_tables:
            try:
                # Query table with limit 0 to get structure without data
                result = habit_service.supabase.table(table_name).select("*").limit(1).execute()

                if result.data or result.data == []:
                    # Table exists - now get one row to see the column structure
                    sample = habit_service.supabase.table(table_name).select("*").limit(1).execute()

                    if sample.data and len(sample.data) > 0:
                        row = sample.data[0]
                        columns = []
                        for col_name, value in row.items():
                            # Infer type from Python type
                            col_type = type(value).__name__ if value is not None else "unknown"
                            # Map Python types to SQL types
                            type_mapping = {
                                'int': 'integer',
                                'str': 'text',
                                'bool': 'boolean',
                                'float': 'numeric',
                                'dict': 'json',
                                'list': 'array',
                                'NoneType': 'unknown'
                            }
                            sql_type = type_mapping.get(col_type, col_type)

                            columns.append({
                                "column": col_name,
                                "type": sql_type,
                                "sample_value": value
                            })
                    else:
                        # Empty table - use fallback schema
                        columns = []

                    tables[table_name] = columns

            except Exception as e:
                logger.debug(f"Table {table_name} does not exist or is inaccessible: {e}")
                continue

        # If dynamic discovery failed, return hardcoded fallback
        if not tables:
            tables = {
                "habits": [
                    {"column": "id", "type": "integer", "description": "Primary key"},
                    {"column": "title", "type": "text", "description": "Habit name/title"},
                    {"column": "start_time", "type": "time", "description": "Time to start habit (HH:MM:SS)"},
                    {"column": "deadline_time", "type": "time", "description": "Time habit must be completed by (HH:MM:SS)"},
                    {"column": "created_at", "type": "timestamp", "description": "When habit was created"}
                ],
                "habit_completions": [
                    {"column": "id", "type": "integer", "description": "Primary key"},
                    {"column": "habit_id", "type": "integer", "description": "Foreign key to habits.id"},
                    {"column": "date", "type": "date", "description": "Date of completion (YYYY-MM-DD)"},
                    {"column": "completed", "type": "boolean", "description": "Whether habit was completed"},
                    {"column": "proof_path", "type": "text", "description": "Path/URL to proof image"}
                ],
                "reminder_log": [
                    {"column": "id", "type": "integer", "description": "Primary key"},
                    {"column": "habit_id", "type": "integer", "description": "Foreign key to habits.id"},
                    {"column": "date", "type": "date", "description": "Date reminder was sent"},
                    {"column": "reminder_type", "type": "text", "description": "'start' or 'deadline'"}
                ]
            }

        # Document known relationships
        relationships = [
            {
                "from_table": "habit_completions",
                "from_column": "habit_id",
                "to_table": "habits",
                "to_column": "id",
                "relationship_type": "many-to-one"
            },
            {
                "from_table": "reminder_log",
                "from_column": "habit_id",
                "to_table": "habits",
                "to_column": "id",
                "relationship_type": "many-to-one"
            }
        ]

        return json.dumps({
            "success": True,
            "tables": tables,
            "relationships": relationships,
            "note": "Schema discovered dynamically from database"
        })

    except Exception as e:
        logger.error(f"Error discovering database schema: {e}")
        # Fallback schema
        return json.dumps({
            "success": True,
            "tables": {
                "habits": [
                    {"column": "id", "type": "integer"},
                    {"column": "title", "type": "text"},
                    {"column": "start_time", "type": "time"},
                    {"column": "deadline_time", "type": "time"}
                ]
            },
            "error": str(e)
        })


def tool_query_database(query: str) -> str:
    """
    Execute a SELECT query against the database
    SECURITY: Only allows SELECT statements, blocks all mutations
    Dynamically routes to appropriate table based on FROM clause
    """
    try:
        # Security: Validate query is read-only
        query_upper = query.strip().upper()

        # Block any non-SELECT operations
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE'
        ]

        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return json.dumps({
                    "success": False,
                    "error": f"Query rejected: '{keyword}' operations are not allowed. Only SELECT queries permitted."
                })

        # Must start with SELECT
        if not query_upper.startswith('SELECT'):
            return json.dumps({
                "success": False,
                "error": "Query rejected: Only SELECT queries are allowed."
            })

        logger.info(f"Executing query: {query}")

        # Extract table name from FROM clause dynamically
        # Match "FROM <table_name>" pattern (case-insensitive)
        import re
        from_match = re.search(r'FROM\s+([a-z_]+)', query, re.IGNORECASE)

        if not from_match:
            return json.dumps({
                "success": False,
                "error": "Unable to parse table name from query. Use format: SELECT ... FROM table_name"
            })

        table_name = from_match.group(1).lower()

        # Try to execute the query on the table
        # If the table doesn't exist, Supabase will return an error

        # Extract column selection
        # Match SELECT <columns> FROM pattern
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)

        if not select_match:
            columns = "*"
        else:
            columns_str = select_match.group(1).strip()
            # If it's *, use *; otherwise, pass the column list
            columns = "*" if columns_str == "*" else columns_str

        # Execute query using Supabase query builder
        result = habit_service.supabase.table(table_name).select(columns).execute()

        return json.dumps({
            "success": True,
            "data": result.data,
            "count": len(result.data) if result.data else 0
        })

    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


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


def tool_get_strikes(habit_id: Optional[int] = None, days: Optional[int] = None) -> str:
    """Get strike count and history"""
    try:
        result = habit_service.get_strike_count(habit_id=habit_id, days=days)
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting strikes: {e}")
        return json.dumps({"success": False, "error": str(e)})


def call_tool(name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    """
    Route tool calls to appropriate functions

    Args:
        name: Tool function name
        arguments: Tool arguments from LLM
        context: Additional context (e.g., media URLs from WhatsApp)
    """
    if name == "add_habit":
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
    elif name == "set_habit_schedule":
        return tool_set_habit_schedule(**arguments)
    elif name == "get_current_time":
        return tool_get_current_time()
    elif name == "get_strikes":
        return tool_get_strikes(**arguments)
    elif name == "get_database_schema":
        return tool_get_database_schema()
    elif name == "query_database":
        return tool_query_database(**arguments)
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

            # Use Responses API
            # Extract system prompt if it exists in messages
            system_instructions = None
            input_messages = messages
            if messages and messages[0].get("role") == "system":
                system_instructions = messages[0].get("content")
                input_messages = messages[1:]  # Skip system message in input

            response = client.responses.create(
                model="gpt-4o-mini",
                input=input_messages if input_messages else messages,
                instructions=system_instructions,
                tools=TOOLS
            )

            # Process output items from Responses API
            has_function_calls = False
            final_text_content = None

            for item in response.output:
                if item.type == "message":
                    # Extract text content from message
                    if hasattr(item, 'content') and item.content:
                        final_text_content = item.content[0].text if hasattr(item.content[0], 'text') else None
                elif item.type == "function_call":
                    # Mark that we have function calls
                    has_function_calls = True

            # If no function calls, we have a final text response
            if not has_function_calls:
                final_content = final_text_content or "I'm not sure how to help with that."
                if verbose:
                    print(f"[Round {iteration}] Model returned final response")

                # Update conversation history with user message and final assistant response
                conversation_history.append(user_message)
                conversation_history.append({"role": "assistant", "content": final_content})

                return final_content, conversation_history

            # Model wants to call tools - process function calls
            if verbose:
                function_call_count = sum(1 for item in response.output if item.type == "function_call")
                print(f"[Round {iteration}] Model requested {function_call_count} function call(s)")

            # Append all output items to messages (including function calls)
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

    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        conversation_history.append(user_message)
        conversation_history.append({"role": "assistant", "content": error_msg})
        return error_msg, conversation_history


def create_new_conversation() -> List[Dict[str, Any]]:
    """Create a new conversation with system prompt initialized"""
    return [{"role": "system", "content": SYSTEM_PROMPT}]
