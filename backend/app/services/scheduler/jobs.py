"""
Scheduler Job Definitions
Contains all scheduled job functions for habit reminders and cleanup
"""
import logging
from app.core.config import settings
from app.services.habits import reminders as reminders_service
from app.services.habits.strikes import check_missed_deadlines as check_missed_deadlines_service
from app.services.habits import repository
from app.services.notifications.service import NotificationService
from app.utils.timezone import get_pacific_today_date

logger = logging.getLogger(__name__)

# Twilio/WhatsApp integration
try:
    from app.services.external.whatsapp import send_whatsapp_message as _send_whatsapp, is_twilio_configured
    WHATSAPP_ENABLED = is_twilio_configured()
    if WHATSAPP_ENABLED:
        logger.info("WhatsApp messaging enabled for scheduler")
    else:
        logger.warning("Twilio credentials not found. WhatsApp reminders will be disabled.")
except ImportError:
    logger.warning("WhatsApp service not available. WhatsApp reminders will be disabled.")
    WHATSAPP_ENABLED = False


def send_whatsapp_message(message: str) -> bool:
    """
    Send a WhatsApp message via Twilio

    Args:
        message: The message text to send

    Returns:
        True if sent successfully, False otherwise
    """
    if not WHATSAPP_ENABLED or not settings.WHATSAPP_RECIPIENT:
        logger.warning("Cannot send WhatsApp message - Twilio client or recipient not configured")
        return False

    try:
        _send_whatsapp(settings.WHATSAPP_RECIPIENT, message)
        logger.info(f"WhatsApp message sent")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False


def check_and_send_reminders():
    """
    Check for habits needing reminders and send them
    Called every N seconds by the scheduler
    """
    try:
        logger.info("[SCHEDULER] Checking for habits needing reminders...")

        # Create notification service with WhatsApp callback
        notification_service = NotificationService(send_whatsapp_message)

        # Get habits that need reminders
        habits_to_remind = reminders_service.get_habits_needing_reminders()

        if not habits_to_remind:
            return

        logger.info(f"[SCHEDULER] Found {len(habits_to_remind)} reminder(s) to send")

        # Send reminder for each habit
        for reminder in habits_to_remind:
            habit_id = reminder["habit_id"]
            habit_title = reminder["habit_title"]
            reminder_type = reminder["reminder_type"]

            logger.info(f"[SCHEDULER] Sending {reminder_type} reminder for: {habit_title}")

            # Send via notification service
            sent = notification_service.send_reminder(habit_title, reminder_type)

            if sent:
                logger.info(f"[SCHEDULER] WhatsApp reminder sent for: {habit_title}")
            else:
                logger.warning(f"[SCHEDULER] Failed to send WhatsApp reminder for: {habit_title}")

            # Mark reminder as sent in database (regardless of WhatsApp success)
            # This prevents repeated attempts for the same reminder
            try:
                reminders_service.mark_reminder_sent(habit_id, reminder_type)
                logger.info(f"[SCHEDULER] Marked {reminder_type} reminder as sent for habit_id={habit_id}")
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to mark reminder as sent: {e}")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in check_and_send_reminders: {e}", exc_info=True)


def check_missed_deadlines():
    """
    Check for habits that missed their deadline and log strikes
    Called periodically (e.g., every 10 seconds)

    Wrapper that provides WhatsApp notification callback
    """
    # Call the strikes service with WhatsApp callback
    check_missed_deadlines_service(send_notification_callback=send_whatsapp_message)


def cleanup_punishment_habits():
    """
    Delete punishment habits that have expired (auto_delete_at <= today)
    Called once daily at 11:59 PM, but also catches up on missed cleanups
    if server was down
    """
    try:
        logger.info("[SCHEDULER] Cleaning up expired punishment habits...")

        today = get_pacific_today_date()

        # Find all expired punishment habits using repository
        expired_habits = repository.get_expired_punishment_habits(today)

        if not expired_habits:
            logger.info("[SCHEDULER] No expired punishment habits to clean up")
            return

        logger.info(f"[SCHEDULER] Found {len(expired_habits)} expired punishment habit(s)")

        # Delete each expired habit
        for habit in expired_habits:
            habit_id = habit["id"]
            habit_title = habit["title"]
            auto_delete_at = habit.get("auto_delete_at")

            try:
                repository.delete_habit(habit_id)
                logger.info(f"[SCHEDULER] Deleted punishment habit: {habit_title} (ID: {habit_id}, expired: {auto_delete_at})")
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to delete habit {habit_id}: {e}")

        logger.info("[SCHEDULER] Punishment habit cleanup completed")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in cleanup_punishment_habits: {e}", exc_info=True)


def check_all():
    """
    Combined check for reminders and missed deadlines
    Runs both checks together every N seconds
    """
    check_and_send_reminders()
    check_missed_deadlines()
