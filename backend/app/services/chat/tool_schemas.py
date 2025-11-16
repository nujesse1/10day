"""
Tool definitions for the chat LLM
Defines the functions/tools available to the language model
"""

# Define tools that the LLM can call (Responses API format)
TOOLS = [
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
    {
        "type": "function",
        "name": "complete_habit_from_image",
        "description": "Intelligently analyze an image, identify ALL habits it proves, match to existing habits, and mark complete. Can identify and complete MULTIPLE habits from a single image. Use this when user sends an image without specifying which habit(s).",
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
