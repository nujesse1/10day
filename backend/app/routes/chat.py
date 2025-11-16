"""
Chat Routes - Direct API access to chat service
"""
import logging
from fastapi import APIRouter, HTTPException
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    NewConversationResponse
)
from app.services.chat import process_user_input, create_new_conversation

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    Process a chat message and return the response

    This endpoint provides direct access to the chat service without WhatsApp.
    It can be used for web interfaces, CLI tools, or testing.

    Args:
        request: Chat request with message and optional conversation history

    Returns:
        ChatResponse with assistant's reply and updated conversation history

    Examples:
        New conversation:
        ```json
        {
            "message": "What are my habits today?",
            "conversation_history": null
        }
        ```

        Continuing conversation:
        ```json
        {
            "message": "Mark reading as complete",
            "conversation_history": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "What are my habits today?"},
                {"role": "assistant", "content": "You have 3 habits..."}
            ]
        }
        ```

        With media (proof verification):
        ```json
        {
            "message": "Here's proof I completed my workout",
            "media_urls": ["https://example.com/workout-photo.jpg"],
            "conversation_history": [...]
        }
        ```
    """
    try:
        # If no conversation history provided, create a new one
        conversation_history = request.conversation_history
        if conversation_history is None:
            logger.info("[CHAT] Creating new conversation")
            conversation_history = create_new_conversation()

        logger.info(f"[CHAT] Processing message: {request.message[:100]}...")

        # Process the message
        response_text, updated_history = process_user_input(
            user_input=request.message,
            conversation_history=conversation_history,
            verbose=request.verbose,
            media_urls=request.media_urls
        )

        logger.info(f"[CHAT] Response generated: {response_text[:100]}...")

        return ChatResponse(
            response=response_text,
            conversation_history=updated_history
        )

    except Exception as e:
        logger.error(f"[CHAT ERROR] Failed to process message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/conversation", response_model=NewConversationResponse)
async def create_conversation():
    """
    Create a new conversation with initialized system prompt

    Returns:
        NewConversationResponse with empty conversation history ready to use

    Example response:
        ```json
        {
            "conversation_history": [
                {"role": "system", "content": "You are a helpful habit tracking assistant..."}
            ],
            "message": "New conversation created"
        }
        ```
    """
    try:
        logger.info("[CHAT] Creating new conversation")
        conversation_history = create_new_conversation()

        return NewConversationResponse(
            conversation_history=conversation_history,
            message="New conversation created"
        )

    except Exception as e:
        logger.error(f"[CHAT ERROR] Failed to create conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversation creation failed: {str(e)}")
