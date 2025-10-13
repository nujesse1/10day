#!/usr/bin/env python3
"""
Drill Sergeant CLI - Natural language habit tracker using OpenAI function calling
"""
import os
from dotenv import load_dotenv
from chat_engine import process_user_input, create_new_conversation

# Load environment variables
load_dotenv()

# Backend API base URL
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def main():
    """Main CLI loop"""
    print("🎖️  Drill Sergeant CLI v0")
    print("Natural language habit tracker")
    print(f"Connected to: {API_BASE}")
    print("Type 'quit' or 'exit' to leave\n")

    # Initialize conversation history with system prompt
    conversation_history = create_new_conversation()

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("🎖️  Dismissed!")
                break

            # Process input with tool calling and conversation history (verbose mode for CLI)
            result, conversation_history = process_user_input(user_input, conversation_history, verbose=True)
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
