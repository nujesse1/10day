"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    # Database
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # AI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # WhatsApp / Twilio
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER: str = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
    WHATSAPP_RECIPIENT: str = os.getenv("WHATSAPP_RECIPIENT", "")

    # Crypto
    BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "")
    PUNISHMENT_WALLET_PRIVATE_KEY: str = os.getenv("PUNISHMENT_WALLET_PRIVATE_KEY", "")
    PUNISHMENT_RECEIVING_ADDRESS: str = os.getenv("PUNISHMENT_RECEIVING_ADDRESS", "")


# Create a global settings instance
settings = Settings()
