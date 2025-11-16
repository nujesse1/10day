"""
Habits module - Core habit management functionality
"""
from . import repository
from . import service
from . import reminders
from . import strikes
from . import punishments

# Export commonly used functions for convenience
from .service import (
    find_habit_by_llm,
    add_habit,
    remove_habit_by_title,
    complete_habit_by_title,
    get_today_habits,
    get_daily_summary,
    set_habit_schedule
)

from .reminders import (
    get_habits_needing_reminders,
    mark_reminder_sent
)

from .strikes import (
    log_strike,
    get_strike_count,
    get_habit_strikes,
    get_today_strike_count,
    check_missed_deadlines
)

from .punishments import assign_punishment

# Re-export supabase for backwards compatibility
from app.core.dependencies import supabase_client as supabase

__all__ = [
    # Modules
    'repository',
    'service',
    'reminders',
    'strikes',
    'punishments',

    # Service functions
    'find_habit_by_llm',
    'add_habit',
    'remove_habit_by_title',
    'complete_habit_by_title',
    'get_today_habits',
    'get_daily_summary',
    'set_habit_schedule',

    # Reminder functions
    'get_habits_needing_reminders',
    'mark_reminder_sent',

    # Strike functions
    'log_strike',
    'get_strike_count',
    'get_habit_strikes',
    'get_today_strike_count',
    'check_missed_deadlines',

    # Punishment functions
    'assign_punishment',

    # Database client
    'supabase'
]
