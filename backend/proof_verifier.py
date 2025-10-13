"""
Proof Verification Service - LLM-based image verification for habit completion
Uses GPT-4 Vision to verify that submitted proof images are legitimate
"""
import os
import base64
import requests
from typing import Optional, Union
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Twilio credentials for media URL downloads
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

logger = logging.getLogger(__name__)


class ProofVerification(BaseModel):
    """Structured output model for proof verification"""
    verified: bool
    confidence: str  # "high" | "medium" | "low"
    reasoning: str


class ImageAnalysis(BaseModel):
    """Structured output for analyzing what habit an image represents"""
    habit_identified: str  # Natural language description of what habit this proves
    activity_type: str  # e.g., "exercise", "meditation", "reading", "nutrition"
    key_details: str  # Specific details visible in the image
    confidence: str  # "high" | "medium" | "low"


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
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        raise ValueError("Twilio credentials not configured")

    try:
        response = requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
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


def analyze_image_for_habit(
    image_source: str,
    is_twilio_url: bool = False
) -> ImageAnalysis:
    """
    Analyze an image to identify what habit it represents

    Args:
        image_source: Either a Twilio media URL or local file path
        is_twilio_url: True if image_source is a Twilio URL, False for local path

    Returns:
        ImageAnalysis object with identified habit and details

    Raises:
        Exception if analysis fails
    """
    try:
        # Download or load the image
        if is_twilio_url:
            logger.info(f"[IMAGE ANALYSIS] Downloading image from Twilio: {image_source[:50]}...")
            image_bytes = download_twilio_media(image_source)
            logger.info(f"[IMAGE ANALYSIS] Downloaded {len(image_bytes)} bytes")
        else:
            logger.info(f"[IMAGE ANALYSIS] Loading image from local file: {image_source}")
            image_bytes = load_local_image(image_source)
            logger.info(f"[IMAGE ANALYSIS] Loaded {len(image_bytes)} bytes")

        # Convert to base64
        base64_image = image_to_base64(image_bytes)
        logger.info(f"[IMAGE ANALYSIS] Converted to base64")

        system_prompt = """You are an intelligent image analyzer for a habit tracking system. Your job is to look at an image and determine what habit completion it represents.

Analyze the image carefully and identify:
1. What activity or habit is being demonstrated
2. The type of activity (exercise, meditation, reading, nutrition, etc.)
3. Key details that prove this activity was done

Be specific but concise."""

        user_prompt = """Analyze this image and tell me what habit completion it represents.

Return a JSON object with:
- habit_identified: Natural language description of the habit (e.g., "morning workout", "reading session", "meditation")
- activity_type: Category (e.g., "exercise", "meditation", "reading", "nutrition", "productivity")
- key_details: What specifically is shown in the image
- confidence: "high"/"medium"/"low" - how confident you are this is legitimate proof"""

        logger.info(f"[IMAGE ANALYSIS] Calling GPT-4 Vision for habit identification")
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
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
            response_format=ImageAnalysis,
            max_tokens=300
        )

        analysis = response.choices[0].message.parsed

        logger.info(f"[IMAGE ANALYSIS] ✓ Analysis complete")
        logger.info(f"[IMAGE ANALYSIS] Identified habit: {analysis.habit_identified}")
        logger.info(f"[IMAGE ANALYSIS] Activity type: {analysis.activity_type}")
        logger.info(f"[IMAGE ANALYSIS] Confidence: {analysis.confidence}")

        return analysis

    except Exception as e:
        logger.error(f"[IMAGE ANALYSIS] ✗ Analysis failed: {e}", exc_info=True)
        raise Exception(f"Failed to analyze image: {str(e)}")


def verify_proof(
    image_source: str,
    habit_title: str,
    is_twilio_url: bool = False,
    additional_context: Optional[str] = None
) -> ProofVerification:
    """
    Verify proof image using GPT-4 Vision

    Args:
        image_source: Either a Twilio media URL or local file path
        habit_title: The habit being verified
        is_twilio_url: True if image_source is a Twilio URL, False for local path
        additional_context: Optional additional context about what constitutes valid proof

    Returns:
        ProofVerification object with verified status, confidence, and reasoning

    Raises:
        Exception if verification fails
    """
    try:
        # Download or load the image
        if is_twilio_url:
            logger.info(f"[PROOF VERIFICATION] Downloading proof from Twilio: {image_source[:50]}...")
            image_bytes = download_twilio_media(image_source)
            logger.info(f"[PROOF VERIFICATION] Downloaded {len(image_bytes)} bytes")
        else:
            logger.info(f"[PROOF VERIFICATION] Loading proof from local file: {image_source}")
            image_bytes = load_local_image(image_source)
            logger.info(f"[PROOF VERIFICATION] Loaded {len(image_bytes)} bytes")

        # Convert to base64
        base64_image = image_to_base64(image_bytes)
        logger.info(f"[PROOF VERIFICATION] Converted to base64: {len(base64_image)} characters")

        # Prepare the verification prompt
        system_prompt = """You are a strict proof verification assistant. Your job is to verify whether an image provides legitimate proof that a habit was completed.

You must be rigorous but fair:
- ACCEPT: Clear, legitimate proof that directly shows completion
- REJECT: Screenshots of screenshots, fake/staged proof, irrelevant images, memes, or unclear evidence

Consider context clues, timestamps, and authenticity markers. If you're uncertain, err on the side of caution."""

        user_prompt = f"""Verify if this image is legitimate proof for completing the habit: "{habit_title}"

{f"Additional context: {additional_context}" if additional_context else ""}

Return a JSON object with:
- verified: true/false
- confidence: "high"/"medium"/"low"
- reasoning: Brief explanation (1-2 sentences)"""

        # Call GPT-4 Vision with Pydantic structured output
        logger.info(f"[PROOF VERIFICATION] Starting verification for habit: {habit_title}")
        logger.info(f"[PROOF VERIFICATION] Image source type: {'Twilio URL' if is_twilio_url else 'Local file'}")

        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"  # Request high-detail analysis
                        }
                    }
                ]}
            ],
            response_format=ProofVerification,
            max_tokens=300
        )

        # Get the parsed Pydantic object directly
        verification = response.choices[0].message.parsed

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
