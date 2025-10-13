"""
WhatsApp Integration - Twilio webhook handler for WhatsApp messages
"""
import os
from fastapi import APIRouter, Request, HTTPException
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from chat_engine import process_user_input
from session_store import get_or_create_session, update_session
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Twilio client
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# Initialize Twilio client if credentials are available
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
else:
    logger.warning("Twilio credentials not found. WhatsApp integration will not work.")

# Create router for WhatsApp endpoints
router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook endpoint for receiving WhatsApp messages from Twilio

    Twilio sends messages as form data with fields:
    - From: Sender's WhatsApp number (e.g., "whatsapp:+13128856151")
    - To: Your Twilio WhatsApp number (e.g., "whatsapp:+14155238886")
    - Body: The text message content
    - NumMedia: Number of media attachments (optional)
    - MediaUrl0, MediaUrl1, etc.: URLs to media files (optional)
    """
    from_number = None  # Initialize to avoid UnboundLocalError in exception handler
    try:
        # Parse form data from Twilio
        form_data = await request.form()

        from_number = form_data.get("From")
        to_number = form_data.get("To")
        message_body = form_data.get("Body", "").strip()
        num_media = int(form_data.get("NumMedia", 0))

        logger.info(f"Received WhatsApp message from {from_number}: {message_body}")

        # Validate required fields
        if not from_number:
            raise HTTPException(status_code=400, detail="Missing 'From' field")

        if not message_body and num_media == 0:
            # Empty message with no media
            response_text = "I didn't receive any message. Please send a text message."
        else:
            # Handle media if present
            media_urls = []
            if num_media > 0:
                for i in range(num_media):
                    media_url = form_data.get(f"MediaUrl{i}")
                    if media_url:
                        media_urls.append(media_url)
                        logger.info(f"Media attachment {i}: {media_url}")

            # TODO: Handle media URLs for proof images in the future
            # For now, we just acknowledge them
            if media_urls:
                message_body += f"\n[Received {len(media_urls)} attachment(s)]"

            # Get or create conversation session for this user
            conversation_history = get_or_create_session(from_number)

            # Process the message using the chat engine
            response_text, updated_history = process_user_input(
                message_body,
                conversation_history,
                verbose=False  # Don't print debug info for WhatsApp
            )

            # Update the session with new conversation history
            update_session(from_number, updated_history)

            logger.info(f"Responding to {from_number}: {response_text}")

        # Send response back via Twilio
        if twilio_client:
            message = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=response_text,
                to=from_number
            )
            logger.info(f"Message sent with SID: {message.sid}")
        else:
            logger.error("Cannot send message - Twilio client not initialized")
            raise HTTPException(status_code=500, detail="Twilio client not configured")

        # Return TwiML response (Twilio expects this)
        return {"status": "success", "message_sid": message.sid}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {str(e)}", exc_info=True)

        # Try to send error message to user
        if twilio_client and from_number:
            try:
                twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body="❌ Sorry, I encountered an error processing your message. Please try again.",
                    to=from_number
                )
            except:
                pass

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatsapp/health")
async def whatsapp_health():
    """Health check endpoint for WhatsApp integration"""
    return {
        "status": "ok",
        "twilio_configured": twilio_client is not None,
        "whatsapp_number": TWILIO_WHATSAPP_NUMBER
    }


@router.post("/whatsapp/status")
async def whatsapp_status():
    """
    Twilio status callback endpoint
    Receives delivery status updates for sent messages
    """
    # This is optional - just log status updates
    # You can extend this to track message delivery
    return {"status": "received"}
