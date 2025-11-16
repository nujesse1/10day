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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error processing WhatsApp webhook: {str(e)}", exc_info=True)

        # Try to send error message to user
        if from_number:
            await send_error_message(from_number)

        raise HTTPException(status_code=500, detail=str(e))
