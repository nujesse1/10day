"""
WhatsApp Routes - Twilio webhook endpoints
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from app.services.external.whatsapp import (
    process_whatsapp_webhook,
    send_error_message,
    is_twilio_configured
)
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("")
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
    from_number = None
    try:
        logger.info("[WEBHOOK START] Received webhook request")

        # Parse form data from Twilio
        form_data = await request.form()
        logger.info("[WEBHOOK] Form data parsed")

        # Extract from_number for error handling
        from_number = form_data.get("From")

        # Process webhook via service
        result = await process_whatsapp_webhook(dict(form_data))
        return result

    except ValueError as e:
        # Validation errors (missing fields, etc.)
        logger.error(f"[ERROR] Validation error: {str(e)}")

        # Try to notify user about validation error
        if from_number:
            await send_error_message(from_number)
            # Return 200 so Twilio doesn't retry
            return {"status": "error", "message": "Validation error, user notified"}

        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error processing WhatsApp webhook: {str(e)}", exc_info=True)

        # Try to send error message to user
        error_message_sent = False
        if from_number:
            try:
                await send_error_message(from_number)
                error_message_sent = True
                logger.info("[ERROR HANDLING] Successfully notified user of error")
            except Exception as notify_error:
                logger.error(f"[ERROR HANDLING] Failed to notify user: {str(notify_error)}")

        # If we successfully notified the user, return 200 to prevent Twilio retries
        # Otherwise return 500 so Twilio can retry
        if error_message_sent:
            return {"status": "error", "message": "Processing failed, user notified"}
        else:
            raise HTTPException(status_code=500, detail=str(e))
