"""
WhatsApp Integration - Twilio webhook handler for WhatsApp messages
"""
import os
from fastapi import APIRouter, Request, HTTPException
from twilio.rest import Client
from dotenv import load_dotenv
from chat_engine import process_user_input
from session_store import get_or_create_session, update_session
import logging

# Load environment variables
load_dotenv()

# Configure logging with more verbose output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing config
)
logger = logging.getLogger(__name__)

# Ensure logs flush immediately
import sys
sys.stdout.flush()
sys.stderr.flush()

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
        logger.info("[WEBHOOK START] Received webhook request")
        sys.stdout.flush()

        # Parse form data from Twilio
        form_data = await request.form()
        logger.info("[WEBHOOK] Form data parsed")
        sys.stdout.flush()

        from_number = form_data.get("From")
        to_number = form_data.get("To")
        message_body = form_data.get("Body", "").strip()
        num_media = int(form_data.get("NumMedia", 0))

        logger.info(f"[WEBHOOK] Received WhatsApp message from {from_number}: {message_body}")
        sys.stdout.flush()

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
                logger.info(f"[MEDIA] Received {num_media} media attachment(s)")
                for i in range(num_media):
                    media_url = form_data.get(f"MediaUrl{i}")
                    if media_url:
                        media_urls.append(media_url)
                        logger.info(f"[MEDIA] Attachment {i}: {media_url}")
                sys.stdout.flush()

            # Get or create conversation session for this user
            logger.info(f"[STEP 1] Getting session for {from_number}")
            sys.stdout.flush()
            conversation_history = get_or_create_session(from_number)
            logger.info(f"[STEP 1 DONE] Session retrieved with {len(conversation_history)} messages")
            sys.stdout.flush()

            # Process the message using the chat engine with media URLs
            logger.info(f"[STEP 2] Processing message with chat engine")
            if media_urls:
                logger.info(f"[STEP 2] Including {len(media_urls)} media URL(s) for proof verification")
            sys.stdout.flush()

            response_text, updated_history = process_user_input(
                message_body,
                conversation_history,
                verbose=False,  # Don't print debug info for WhatsApp
                media_urls=media_urls if media_urls else None
            )
            logger.info(f"[STEP 2 DONE] Chat engine returned response: {response_text[:100]}...")
            sys.stdout.flush()

            # Update the session with new conversation history
            logger.info(f"[STEP 3] Updating session with new history")
            sys.stdout.flush()
            update_session(from_number, updated_history)
            logger.info(f"[STEP 3 DONE] Session updated")
            sys.stdout.flush()

            logger.info(f"[STEP 4] Preparing to respond to {from_number}")
            sys.stdout.flush()

        # Send response back via Twilio
        logger.info(f"[STEP 5] Sending message via Twilio")
        sys.stdout.flush()
        if twilio_client:
            logger.info(f"[STEP 5a] Twilio client available, creating message")
            sys.stdout.flush()

            try:
                message = twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body=response_text,
                    to=from_number
                )
                logger.info(f"[STEP 5 DONE] Message sent with SID: {message.sid}")
                sys.stdout.flush()
            except Exception as twilio_error:
                logger.error(f"[STEP 5 ERROR] Twilio send failed: {str(twilio_error)}")
                sys.stdout.flush()
                raise
        else:
            logger.error("[STEP 5 ERROR] Cannot send message - Twilio client not initialized")
            sys.stdout.flush()
            raise HTTPException(status_code=500, detail="Twilio client not configured")

        # Return TwiML response (Twilio expects this)
        return {"status": "success", "message_sid": message.sid}

    except HTTPException as http_exc:
        logger.error(f"[ERROR] HTTP Exception: {http_exc.detail}")
        sys.stdout.flush()
        raise
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error processing WhatsApp webhook: {str(e)}", exc_info=True)
        sys.stdout.flush()

        # Try to send error message to user
        if twilio_client and from_number:
            logger.info(f"[ERROR RECOVERY] Attempting to send error message to {from_number}")
            sys.stdout.flush()
            try:
                twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body="❌ Sorry, I encountered an error processing your message. Please try again.",
                    to=from_number
                )
                logger.info(f"[ERROR RECOVERY] Error message sent")
                sys.stdout.flush()
            except Exception as recovery_error:
                logger.error(f"[ERROR RECOVERY] Failed to send error message: {str(recovery_error)}")
                sys.stdout.flush()

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
