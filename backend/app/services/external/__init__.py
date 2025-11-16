"""
External integrations module
Handles connections to external services (WhatsApp, Blockchain, Vision APIs)
"""
from . import whatsapp
from . import blockchain
from . import vision

__all__ = ['whatsapp', 'blockchain', 'vision']
