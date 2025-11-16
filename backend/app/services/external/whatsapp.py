"""
WhatsApp Service - Twilio messaging logic
"""
import logging
import sys
from twilio.rest import Client
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# Ensure logs flush immediately
sys.stdout.flush()
sys.stderr.flush()

# Initialize Twilio client if credentials are available
twilio_client = None
if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
    twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
else:
    logger.warning("Twilio credentials not found. WhatsApp integration will not work.")


def send_whatsapp_message(to_number: str, message: str) -> str:
    """
    Send a WhatsApp message via Twilio

    Args:
        to_number: Recipient WhatsApp number (e.g., "whatsapp:+13128856151")
        message: Message text to send

    Returns:
        Message SID from Twilio

    Raises:
        Exception if Twilio client not configured or send fails
    """
    if not twilio_client:
        raise Exception("Twilio client not configured")

    logger.info(f"[TWILIO] Sending message to {to_number}")
    sys.stdout.flush()

    try:
        twilio_message = twilio_client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER or "whatsapp:+14155238886",
            body=message,
            to=to_number
        )
        logger.info(f"[TWILIO] Message sent with SID: {twilio_message.sid}")
        sys.stdout.flush()
        return twilio_message.sid
    except Exception as e:
        logger.error(f"[TWILIO] Send failed: {str(e)}")
        sys.stdout.flush()
        raise


def is_twilio_configured() -> bool:
    """Check if Twilio client is configured"""
    return twilio_client is not None


def _extract_message_data(form_data: dict) -> tuple[str, str, int]:
    """
    Extract and validate message data from Twilio form data

    Returns:
        Tuple of (from_number, message_body, num_media)

    Raises:
        ValueError: If required fields are missing
    """
    from_number = form_data.get("From")
    message_body = form_data.get("Body", "").strip()
    num_media = int(form_data.get("NumMedia", 0))

    logger.info(f"[WEBHOOK] Received WhatsApp message from {from_number}: {message_body}")

    if not from_number:
        raise ValueError("Missing 'From' field")

    return from_number, message_body, num_media


def _collect_media_urls(form_data: dict, num_media: int) -> list[str]:
    """
    Extract media URLs from form data

    Returns:
        List of media URLs
    """
    media_urls = []
    if num_media > 0:
        logger.info(f"[MEDIA] Received {num_media} media attachment(s)")
        for i in range(num_media):
            media_url = form_data.get(f"MediaUrl{i}")
            if media_url:
                media_urls.append(media_url)
                logger.info(f"[MEDIA] Attachment {i}: {media_url}")
    return media_urls


def _process_message(from_number: str, message_body: str, media_urls: list[str] | None) -> str:
    """
    Process user message through chat engine and update session

    Returns:
        Response text to send back to user
    """
    from app.services.chat import process_user_input
    from app.utils.session_store import get_or_create_session, update_session

    # Get conversation session
    logger.info(f"[STEP 1] Getting session for {from_number}")
    conversation_history = get_or_create_session(from_number)
    logger.info(f"[STEP 1 DONE] Session retrieved with {len(conversation_history)} messages")

    # Process with chat engine
    logger.info(f"[STEP 2] Processing message with chat engine")
    if media_urls:
        logger.info(f"[STEP 2] Including {len(media_urls)} media URL(s) for proof verification")

    response_text, updated_history = process_user_input(
        message_body,
        conversation_history,
        verbose=False,
        media_urls=media_urls
    )
    logger.info(f"[STEP 2 DONE] Chat engine returned response: {response_text[:100]}...")

    # Update session
    logger.info(f"[STEP 3] Updating session with new history")
    update_session(from_number, updated_history)
    logger.info(f"[STEP 3 DONE] Session updated")

    return response_text


def _send_response(from_number: str, response_text: str) -> str:
    """
    Send response message via Twilio

    Returns:
        Message SID

    Raises:
        Exception: If Twilio not configured or send fails
    """
    logger.info(f"[STEP 5] Sending message via Twilio")

    if not is_twilio_configured():
        logger.error("[STEP 5 ERROR] Cannot send message - Twilio client not initialized")
        raise Exception("Twilio client not configured")

    message_sid = send_whatsapp_message(from_number, response_text)
    logger.info(f"[STEP 5 DONE] Message sent with SID: {message_sid}")
    return message_sid


async def process_whatsapp_webhook(form_data: dict) -> dict:
    """
    Process incoming WhatsApp webhook from Twilio

    Args:
        form_data: Form data dictionary from Twilio webhook

    Returns:
        Dictionary with status and message_sid

    Raises:
        ValueError: If required fields are missing
        Exception: If processing or sending fails
    """
    # Extract and validate message data
    from_number, message_body, num_media = _extract_message_data(form_data)

    # Handle empty message
    if not message_body and num_media == 0:
        response_text = "I didn't receive any message. Please send a text message."
    else:
        # Collect media attachments
        media_urls = _collect_media_urls(form_data, num_media)

        # Process message through chat engine
        response_text = _process_message(from_number, message_body, media_urls if media_urls else None)

    # Send response
    message_sid = _send_response(from_number, response_text)

    return {"status": "success", "message_sid": message_sid}


async def send_error_message(from_number: str) -> None:
    """
    Send error message to user when webhook processing fails

    Args:
        from_number: User's WhatsApp number
    """
    if is_twilio_configured() and from_number:
        logger.info(f"[ERROR RECOVERY] Attempting to send error message to {from_number}")
        try:
            send_whatsapp_message(
                from_number,
                "❌ Sorry, I encountered an error processing your message. Please try again."
            )
            logger.info(f"[ERROR RECOVERY] Error message sent")
        except Exception as recovery_error:
            logger.error(f"[ERROR RECOVERY] Failed to send error message: {str(recovery_error)}")
