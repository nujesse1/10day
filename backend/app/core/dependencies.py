"""
Dependency injection for shared clients and resources
"""
from supabase import create_client, Client
from openai import OpenAI
from app.core.config import settings


def get_supabase_client() -> Client:
    """Get Supabase client instance"""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def get_openai_client() -> OpenAI:
    """Get OpenAI client instance"""
    return OpenAI(api_key=settings.OPENAI_API_KEY)


# Create singleton instances for internal use
supabase_client = get_supabase_client()
openai_client = get_openai_client()
