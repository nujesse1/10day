"""
Tool handler implementations for the chat LLM
Each function implements a specific tool that the LLM can call
"""
import json
from typing import Optional, Dict, Any
import logging
import re

from app.services import habits
from app.services.external.vision import verify_proof, analyze_image_for_habit
from app.utils.timezone import get_pacific_now

logger = logging.getLogger(__name__)

# Alias for backward compatibility within this module
habit_service = habits


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

        # Get habit details to fetch deadline_time
        habits_data = habit_service.get_today_habits()
        existing_habits = habits_data.get("habits", [])

        # Find the matching habit to get deadline
        matched_habit = habit_service.find_habit_by_llm(title, existing_habits)
        deadline_time = matched_habit.get("deadline_time") if matched_habit else None

        # Verify the proof using GPT-4 Vision with deadline checking
        verification = verify_proof(
            image_source=proof_source,
            habit_title=title,
            is_twilio_url=is_twilio_url,
            deadline_time=deadline_time
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
        now = get_pacific_now()
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


def _discover_table_schema(table_name: str) -> Optional[list]:
    """
    Discover schema for a single table by querying it

    Args:
        table_name: Name of table to discover

    Returns:
        List of column definitions or None if table doesn't exist
    """
    try:
        # Query table with limit 1 to get structure
        result = habit_service.supabase.table(table_name).select("*").limit(1).execute()

        if result.data or result.data == []:
            # Table exists - get one row to see column structure
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
                return columns
            else:
                # Empty table - return empty list
                return []
        return None
    except Exception as e:
        logger.debug(f"Table {table_name} does not exist or is inaccessible: {e}")
        return None


def _get_fallback_schema() -> Dict[str, list]:
    """Get hardcoded fallback schema when dynamic discovery fails"""
    return {
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


def _get_schema_relationships() -> list:
    """Get database relationship definitions"""
    return [
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
            columns = _discover_table_schema(table_name)
            if columns is not None:
                tables[table_name] = columns

        # If dynamic discovery failed, return hardcoded fallback
        if not tables:
            tables = _get_fallback_schema()

        # Document known relationships
        relationships = _get_schema_relationships()

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


def _validate_query_security(query: str) -> None:
    """
    Validate that a query is read-only and safe to execute

    Args:
        query: SQL query to validate

    Raises:
        ValueError: If query is not safe to execute
    """
    query_upper = query.strip().upper()

    # Block any non-SELECT operations
    dangerous_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE'
    ]

    for keyword in dangerous_keywords:
        if keyword in query_upper:
            raise ValueError(f"Query rejected: '{keyword}' operations are not allowed. Only SELECT queries permitted.")

    # Must start with SELECT
    if not query_upper.startswith('SELECT'):
        raise ValueError("Query rejected: Only SELECT queries are allowed.")


def _parse_query_components(query: str) -> tuple[str, str]:
    """
    Parse table name and columns from SQL query

    Args:
        query: SQL SELECT query

    Returns:
        Tuple of (table_name, columns_str)

    Raises:
        ValueError: If query cannot be parsed
    """
    # Extract table name from FROM clause
    from_match = re.search(r'FROM\s+([a-z_]+)', query, re.IGNORECASE)

    if not from_match:
        raise ValueError("Unable to parse table name from query. Use format: SELECT ... FROM table_name")

    table_name = from_match.group(1).lower()

    # Extract column selection
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)

    if not select_match:
        columns = "*"
    else:
        columns_str = select_match.group(1).strip()
        columns = "*" if columns_str == "*" else columns_str

    return table_name, columns


def tool_query_database(query: str) -> str:
    """
    Execute a SELECT query against the database
    SECURITY: Only allows SELECT statements, blocks all mutations
    Dynamically routes to appropriate table based on FROM clause
    """
    try:
        # Security: Validate query is read-only
        _validate_query_security(query)

        logger.info(f"Executing query: {query}")

        # Parse query components
        table_name, columns = _parse_query_components(query)

        # Execute query using Supabase query builder
        result = habit_service.supabase.table(table_name).select(columns).execute()

        return json.dumps({
            "success": True,
            "data": result.data,
            "count": len(result.data) if result.data else 0
        })

    except ValueError as e:
        # Security validation errors
        return json.dumps({
            "success": False,
            "error": str(e)
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
    1. Get existing habits from database
    2. Analyze image AND message together to match to habit(s) - CAN MATCH MULTIPLE
    3. Verify proof is legitimate for EACH matched habit
    4. Mark complete ALL verified habits

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

        # Step 2: Get existing habits from database
        logger.info(f"[SMART COMPLETION] Step 1: Getting existing habits...")
        habits_data = habit_service.get_today_habits()
        existing_habits = habits_data.get("habits", [])

        if not existing_habits:
            return json.dumps({
                "success": False,
                "error": "No habits found to match against. Add some habits first."
            })

        # Step 3: Analyze the image AND message to identify ALL matching habits
        logger.info(f"[SMART COMPLETION] Step 2: Analyzing image and message to match habits...")
        analysis = analyze_image_for_habit(
            image_source=proof_source,
            user_message=user_message,
            available_habits=existing_habits,
            is_twilio_url=is_twilio_url
        )

        matched_habit_titles = analysis.matched_habit_titles
        logger.info(f"[SMART COMPLETION] Matched {len(matched_habit_titles)} habit(s): {matched_habit_titles}")
        logger.info(f"[SMART COMPLETION] Identified: {analysis.habit_identified}")
        logger.info(f"[SMART COMPLETION] Activity type: {analysis.activity_type}")
        logger.info(f"[SMART COMPLETION] Details: {analysis.key_details}")
        logger.info(f"[SMART COMPLETION] Multiple habits detected: {analysis.multiple_habits_detected}")

        if not matched_habit_titles:
            return json.dumps({
                "success": False,
                "error": "No habits matched from the image. Available habits: " + ", ".join([h['title'] for h in existing_habits]),
                "identified_habit": analysis.habit_identified,
                "confidence": analysis.confidence
            })

        # Step 4: Verify and complete EACH matched habit
        completed_habits = []
        failed_verifications = []

        for habit_title in matched_habit_titles:
            logger.info(f"[SMART COMPLETION] Processing habit: {habit_title}")

            # Find the habit in our list
            matched_habit = next((h for h in existing_habits if h['title'] == habit_title), None)

            if not matched_habit:
                logger.warning(f"[SMART COMPLETION] Habit '{habit_title}' not found in database")
                failed_verifications.append({
                    "habit": habit_title,
                    "reason": "Habit not found in database",
                    "confidence": "n/a"
                })
                continue

            # Verify proof for this specific habit
            logger.info(f"[SMART COMPLETION] Step 3: Verifying proof for '{habit_title}'...")
            deadline_time = matched_habit.get('deadline_time')

            verification = verify_proof(
                image_source=proof_source,
                habit_title=matched_habit['title'],
                is_twilio_url=is_twilio_url,
                additional_context=f"User said: '{user_message}'. Image shows: {analysis.key_details}. Note: This image may prove multiple habits.",
                deadline_time=deadline_time
            )

            if not verification.verified:
                logger.warning(f"[SMART COMPLETION] Proof rejected for '{habit_title}': {verification.reasoning}")
                failed_verifications.append({
                    "habit": matched_habit['title'],
                    "reason": verification.reasoning,
                    "confidence": verification.confidence
                })
                continue

            # Mark complete
            logger.info(f"[SMART COMPLETION] Proof verified for '{habit_title}': {verification.reasoning}")
            logger.info(f"[SMART COMPLETION] Step 4: Marking habit '{habit_title}' complete...")
            result = habit_service.complete_habit_by_title(matched_habit['title'], proof_source)

            completed_habits.append({
                "habit": matched_habit['title'],
                "verification_confidence": verification.confidence,
                "reasoning": verification.reasoning
            })

        # Return comprehensive results
        if len(completed_habits) > 0:
            return json.dumps({
                "success": True,
                "message": f"Completed {len(completed_habits)} habit(s) from image",
                "completed_habits": completed_habits,
                "failed_verifications": failed_verifications if failed_verifications else [],
                "analysis": {
                    "identified": analysis.habit_identified,
                    "total_habits_detected": len(matched_habit_titles),
                    "details": analysis.key_details,
                    "multiple_habits": analysis.multiple_habits_detected,
                    "analysis_confidence": analysis.confidence
                }
            })
        else:
            return json.dumps({
                "success": False,
                "error": "All habit verifications failed",
                "failed_verifications": failed_verifications,
                "analysis": {
                    "identified": analysis.habit_identified,
                    "details": analysis.key_details,
                    "analysis_confidence": analysis.confidence
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
    Route tool calls to appropriate handler functions

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
