"""
Proof Verification Service - LLM-based image verification for habit completion
Uses GPT-4 Vision to verify that submitted proof images are legitimate
"""
import os
import base64
import requests
from typing import Optional
import logging
from datetime import datetime, timedelta
from app.core.dependencies import openai_client as client
from app.core.config import settings
from app.core.constants import LLM_MODEL_VISION, DEADLINE_GRACE_PERIOD_MINUTES
from app.models.proof import ProofVerification, ImageAnalysis
from app.utils.timezone import get_pacific_now
from app.utils.prompts import (
    VISION_IMAGE_ANALYSIS_SYSTEM_PROMPT,
    VISION_PROOF_VERIFICATION_SYSTEM_PROMPT,
    format_image_analysis_prompt,
    format_proof_verification_prompt
)

logger = logging.getLogger(__name__)


def download_twilio_media(media_url: str) -> bytes:
    """
    Download media from Twilio URL (requires authentication)

    Args:
        media_url: Twilio media URL (e.g., https://api.twilio.com/2010-04-01/Accounts/.../Media/...)

    Returns:
        Image bytes

    Raises:
        Exception if download fails or credentials missing
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise ValueError("Twilio credentials not configured")

    try:
        response = requests.get(
            media_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=10
        )
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        logger.error(f"Failed to download Twilio media: {e}")
        raise Exception(f"Failed to download proof image: {str(e)}")


def load_local_image(file_path: str) -> bytes:
    """
    Load image from local file path

    Args:
        file_path: Path to local image file

    Returns:
        Image bytes

    Raises:
        Exception if file doesn't exist or can't be read
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Proof image not found: {file_path}")

    try:
        with open(file_path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read local image: {e}")
        raise Exception(f"Failed to read proof image: {str(e)}")


def image_to_base64(image_bytes: bytes) -> str:
    """
    Convert image bytes to base64 string

    Args:
        image_bytes: Raw image bytes

    Returns:
        Base64 encoded string
    """
    return base64.b64encode(image_bytes).decode('utf-8')


def _load_and_encode_image(image_source: str, is_twilio_url: bool, operation_name: str = "OPERATION") -> str:
    """
    Shared helper to load and encode image from either Twilio URL or local path

    Args:
        image_source: Either a Twilio media URL or local file path
        is_twilio_url: True if image_source is a Twilio URL, False for local path
        operation_name: Name to use in log messages (e.g., "IMAGE ANALYSIS", "PROOF VERIFICATION")

    Returns:
        Base64 encoded image string

    Raises:
        Exception if loading or encoding fails
    """
    # Download or load the image
    if is_twilio_url:
        logger.info(f"[{operation_name}] Downloading image from Twilio: {image_source[:50]}...")
        image_bytes = download_twilio_media(image_source)
        logger.info(f"[{operation_name}] Downloaded {len(image_bytes)} bytes")
    else:
        logger.info(f"[{operation_name}] Loading image from local file: {image_source}")
        image_bytes = load_local_image(image_source)
        logger.info(f"[{operation_name}] Loaded {len(image_bytes)} bytes")

    # Convert to base64
    base64_image = image_to_base64(image_bytes)
    logger.info(f"[{operation_name}] Converted to base64")

    return base64_image


def _build_habit_analysis_prompt(user_message: str, habit_titles: list) -> tuple[str, str]:
    """
    Build system and user prompts for habit analysis

    Args:
        user_message: Message sent by user
        habit_titles: List of available habit titles

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    return VISION_IMAGE_ANALYSIS_SYSTEM_PROMPT, format_image_analysis_prompt(user_message, habit_titles)


def _call_vision_api_for_analysis(base64_image: str, system_prompt: str, user_prompt: str) -> ImageAnalysis:
    """
    Call GPT-4 Vision API for image analysis

    Args:
        base64_image: Base64 encoded image
        system_prompt: System prompt for the model
        user_prompt: User prompt for the model

    Returns:
        ImageAnalysis object

    Raises:
        Exception if API call fails
    """
    logger.info(f"[IMAGE ANALYSIS] Calling GPT-4 Vision for habit identification")

    response = client.beta.chat.completions.parse(
        model=LLM_MODEL_VISION,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "high"
                    }
                }
            ]}
        ],
        response_format=ImageAnalysis
    )

    return response.choices[0].message.parsed


def analyze_image_for_habit(
    image_source: str,
    user_message: str,
    available_habits: list,
    is_twilio_url: bool = False
) -> ImageAnalysis:
    """
    Analyze an image AND user message to identify which habit is being completed

    Args:
        image_source: Either a Twilio media URL or local file path
        user_message: The text message the user sent with the image
        available_habits: List of habit dicts with 'title' field to match against
        is_twilio_url: True if image_source is a Twilio URL, False for local path

    Returns:
        ImageAnalysis object with matched habit and details

    Raises:
        Exception if analysis fails
    """
    try:
        # Step 1: Load and encode image
        base64_image = _load_and_encode_image(image_source, is_twilio_url, "IMAGE ANALYSIS")

        # Step 2: Build prompts
        habit_titles = [h.get('title') for h in available_habits]
        system_prompt, user_prompt = _build_habit_analysis_prompt(user_message, habit_titles)

        # Step 3: Call Vision API
        analysis = _call_vision_api_for_analysis(base64_image, system_prompt, user_prompt)

        logger.info(f"[IMAGE ANALYSIS] ✓ Analysis complete")
        logger.info(f"[IMAGE ANALYSIS] Matched habit: {analysis.matched_habit_title}")
        logger.info(f"[IMAGE ANALYSIS] Identified: {analysis.habit_identified}")
        logger.info(f"[IMAGE ANALYSIS] Activity type: {analysis.activity_type}")
        logger.info(f"[IMAGE ANALYSIS] Confidence: {analysis.confidence}")

        return analysis

    except Exception as e:
        logger.error(f"[IMAGE ANALYSIS] ✗ Analysis failed: {e}", exc_info=True)
        raise Exception(f"Failed to analyze image: {str(e)}")


def _check_deadline_constraint(deadline_time: str) -> Optional[ProofVerification]:
    """
    Check if proof submission is within deadline grace period

    Args:
        deadline_time: Deadline time in HH:MM:SS format (24-hour)

    Returns:
        ProofVerification with rejection if too late, None if OK
    """
    # Use Pacific timezone (consistent with rest of app)
    now_pacific = get_pacific_now()
    current_time = now_pacific.time()

    # Parse deadline time (format: "HH:MM:SS" in 24-hour)
    deadline = datetime.strptime(deadline_time, "%H:%M:%S").time()

    # Create datetime objects for comparison (using today's date)
    current_dt = datetime.combine(now_pacific.date(), current_time)
    deadline_dt = datetime.combine(now_pacific.date(), deadline)

    # Add grace period
    deadline_with_grace = deadline_dt + timedelta(minutes=DEADLINE_GRACE_PERIOD_MINUTES)

    # Check if submission is too late
    if current_dt > deadline_with_grace:
        logger.warning(f"[PROOF VERIFICATION] Submission too late - Current: {current_time.strftime('%H:%M:%S')}, Deadline: {deadline_time}, Grace: +{DEADLINE_GRACE_PERIOD_MINUTES}min")
        return ProofVerification(
            verified=False,
            confidence="high",
            reasoning=f"Proof submitted too late. Deadline was {deadline_time}, current time is {current_time.strftime('%H:%M:%S')} ({DEADLINE_GRACE_PERIOD_MINUTES}-minute grace period expired)."
        )

    logger.info(f"[PROOF VERIFICATION] Timestamp check passed - Current: {current_time.strftime('%H:%M:%S')}, Deadline: {deadline_time} (+{DEADLINE_GRACE_PERIOD_MINUTES}min grace)")
    return None


def _build_verification_prompt(habit_title: str, additional_context: Optional[str] = None) -> tuple[str, str]:
    """
    Build system and user prompts for proof verification

    Args:
        habit_title: The habit being verified
        additional_context: Optional additional context

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    return VISION_PROOF_VERIFICATION_SYSTEM_PROMPT, format_proof_verification_prompt(habit_title, additional_context)


def _call_vision_api_for_verification(base64_image: str, system_prompt: str, user_prompt: str, habit_title: str, is_twilio_url: bool) -> ProofVerification:
    """
    Call GPT-4 Vision API for proof verification

    Args:
        base64_image: Base64 encoded image
        system_prompt: System prompt for the model
        user_prompt: User prompt for the model
        habit_title: The habit being verified (for logging)
        is_twilio_url: Whether source was Twilio URL (for logging)

    Returns:
        ProofVerification object

    Raises:
        Exception if API call fails
    """
    logger.info(f"[PROOF VERIFICATION] Starting verification for habit: {habit_title}")
    logger.info(f"[PROOF VERIFICATION] Image source type: {'Twilio URL' if is_twilio_url else 'Local file'}")

    response = client.beta.chat.completions.parse(
        model=LLM_MODEL_VISION,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "high"
                    }
                }
            ]}
        ],
        response_format=ProofVerification
    )

    return response.choices[0].message.parsed


def verify_proof(
    image_source: str,
    habit_title: str,
    is_twilio_url: bool = False,
    additional_context: Optional[str] = None,
    deadline_time: Optional[str] = None
) -> ProofVerification:
    """
    Verify proof image using GPT-4 Vision with optional deadline checking

    Args:
        image_source: Either a Twilio media URL or local file path
        habit_title: The habit being verified
        is_twilio_url: True if image_source is a Twilio URL, False for local path
        additional_context: Optional additional context about what constitutes valid proof
        deadline_time: Optional deadline time in HH:MM:SS format (24-hour). If provided,
                      checks if proof is submitted within grace period of deadline

    Returns:
        ProofVerification object with verified status, confidence, and reasoning

    Raises:
        Exception if verification fails
    """
    try:
        # Step 1: Check deadline if provided (with grace period)
        if deadline_time:
            deadline_check = _check_deadline_constraint(deadline_time)
            if deadline_check:
                return deadline_check

        # Step 2: Load and encode image
        base64_image = _load_and_encode_image(image_source, is_twilio_url, "PROOF VERIFICATION")

        # Step 3: Build prompts
        system_prompt, user_prompt = _build_verification_prompt(habit_title, additional_context)

        # Step 4: Call Vision API
        verification = _call_vision_api_for_verification(base64_image, system_prompt, user_prompt, habit_title, is_twilio_url)

        # Log detailed results
        logger.info(f"[PROOF VERIFICATION] ✓ Verification complete")
        logger.info(f"[PROOF VERIFICATION] Verified: {verification.verified}")
        logger.info(f"[PROOF VERIFICATION] Confidence: {verification.confidence}")
        logger.info(f"[PROOF VERIFICATION] Reasoning: {verification.reasoning}")

        return verification

    except Exception as e:
        logger.error(f"[PROOF VERIFICATION] ✗ Verification failed: {e}", exc_info=True)
        # Return a failed verification with the error
        return ProofVerification(
            verified=False,
            confidence="low",
            reasoning=f"Verification failed: {str(e)}"
        )
