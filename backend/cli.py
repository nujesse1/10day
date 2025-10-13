#!/usr/bin/env python3
"""
Drill Sergeant CLI - Natural language habit tracker using OpenAI function calling
"""
import os
import re
from dotenv import load_dotenv
from chat_engine import process_user_input, create_new_conversation

# Load environment variables
load_dotenv()

# Backend API base URL
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# Image file extensions to look for
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.heic', '.webp', '.bmp')


def extract_proof_path(user_input: str) -> tuple[str, str | None]:
    """
    Extract proof file path from user input

    Args:
        user_input: The user's message

    Returns:
        Tuple of (cleaned_message, proof_path or None)

    Examples:
        "done workout ~/proof.png" -> ("done workout", "/Users/jesse/proof.png")
        "completed reading" -> ("completed reading", None)
    """
    # Pattern to match file paths (starting with / or ~ and ending with image extension)
    pattern = r'([~/][^\s]+\.(?:' + '|'.join(ext[1:] for ext in IMAGE_EXTENSIONS) + r'))'

    match = re.search(pattern, user_input, re.IGNORECASE)

    if match:
        proof_path = match.group(1)

        # Expand ~ to home directory
        proof_path = os.path.expanduser(proof_path)

        # Check if file exists
        if os.path.exists(proof_path) and os.path.isfile(proof_path):
            # Remove the file path from the message
            cleaned_message = re.sub(pattern, '', user_input).strip()
            # Clean up extra spaces
            cleaned_message = re.sub(r'\s+', ' ', cleaned_message)

            return cleaned_message, proof_path
        else:
            print(f"⚠️  Warning: Proof file not found: {proof_path}")
            return user_input, None

    return user_input, None


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

            # Extract proof file path if present
            cleaned_input, proof_path = extract_proof_path(user_input)

            if proof_path:
                print(f"📸 Detected proof file: {proof_path}")

            # Process input with tool calling and conversation history (verbose mode for CLI)
            # Pass proof_path as media_urls (same interface as WhatsApp)
            media_urls = [proof_path] if proof_path else None

            result, conversation_history = process_user_input(
                cleaned_input,
                conversation_history,
                verbose=True,
                media_urls=media_urls
            )
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
