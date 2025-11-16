"""
Business logic services - New modular structure
"""
# New modular structure
from . import habits
from . import chat
from . import scheduler
from . import notifications
from . import external

# Backward compatibility - export habits module as habit_service
habit_service = habits

__all__ = [
    'habits',
    'chat',
    'scheduler',
    'notifications',
    'external',
    'habit_service'  # Backward compatibility
]
