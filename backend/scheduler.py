"""
Scheduler Service - Automatic habit reminders
Sends WhatsApp messages and logs notifications for CLI users
"""
import os
import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
import habit_service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Twilio/WhatsApp integration
try:
    from twilio.rest import Client
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    WHATSAPP_RECIPIENT = os.getenv("WHATSAPP_RECIPIENT")  # Your WhatsApp number

    twilio_client = None
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized for scheduler")
    else:
        logger.warning("Twilio credentials not found. WhatsApp reminders will be disabled.")
except ImportError:
    logger.warning("Twilio not installed. WhatsApp reminders will be disabled.")
    twilio_client = None

# Global scheduler instance
scheduler = None


def send_whatsapp_message(message: str) -> bool:
    """
    Send a WhatsApp message via Twilio

    Args:
        message: The message text to send

    Returns:
        True if sent successfully, False otherwise
    """
    if not twilio_client or not WHATSAPP_RECIPIENT:
        logger.warning("Cannot send WhatsApp message - Twilio client or recipient not configured")
        return False

    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=message,
            to=WHATSAPP_RECIPIENT
        )
        logger.info(f"WhatsApp message sent: {msg.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False


def check_and_send_reminders():
    """
    Check for habits needing reminders and send them
    Called every minute by the scheduler
    """
    try:
        logger.info("[SCHEDULER] Checking for habits needing reminders...")

        # Get habits that need reminders
        habits_to_remind = habit_service.get_habits_needing_reminders()

        if not habits_to_remind:
            logger.info("[SCHEDULER] No reminders needed at this time")
            return

        logger.info(f"[SCHEDULER] Found {len(habits_to_remind)} reminder(s) to send")

        # Send reminder for each habit
        for reminder in habits_to_remind:
            habit_id = reminder["habit_id"]
            habit_title = reminder["habit_title"]
            reminder_type = reminder["reminder_type"]

            # Craft the message based on reminder type
            if reminder_type == "start":
                message = f"🔔 TIME TO START: {habit_title}\n\nGet moving! This habit is scheduled to start now."
            else:  # deadline
                message = f"⏰ DEADLINE APPROACHING: {habit_title}\n\nTime's up! Complete this habit now and send proof."

            logger.info(f"[SCHEDULER] Sending {reminder_type} reminder for: {habit_title}")

            # Send via WhatsApp
            sent = send_whatsapp_message(message)

            if sent:
                logger.info(f"[SCHEDULER] WhatsApp reminder sent for: {habit_title}")
            else:
                logger.warning(f"[SCHEDULER] Failed to send WhatsApp reminder for: {habit_title}")

            # Mark reminder as sent in database (regardless of WhatsApp success)
            # This prevents repeated attempts for the same reminder
            try:
                habit_service.mark_reminder_sent(habit_id, reminder_type)
                logger.info(f"[SCHEDULER] Marked {reminder_type} reminder as sent for habit_id={habit_id}")
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to mark reminder as sent: {e}")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in check_and_send_reminders: {e}", exc_info=True)


def check_missed_deadlines():
    """
    Check for habits that missed their deadline and log strikes
    Called periodically (e.g., every hour or at end of day)

    Logic:
    - Find habits where deadline_time has passed
    - Check if habit was completed
    - If not completed AND deadline reminder was sent, log a strike
    """
    try:
        from datetime import datetime

        logger.info("[SCHEDULER] Checking for missed deadlines...")

        today = date.today()
        current_time = datetime.now().time()

        # Get today's habits
        habits_data = habit_service.get_today_habits()
        habits = habits_data.get("habits", [])

        # Get today's reminders to see which deadlines were reminded
        reminders = habit_service.supabase.table("reminder_log")\
            .select("*")\
            .eq("date", str(today))\
            .eq("reminder_type", "deadline")\
            .execute()

        reminded_habit_ids = {r["habit_id"] for r in reminders.data}

        # Get today's strikes to avoid duplicate strikes
        existing_strikes = habit_service.supabase.table("strikes")\
            .select("*")\
            .eq("date", str(today))\
            .eq("reason", "missed_deadline")\
            .execute()

        already_striked_ids = {s["habit_id"] for s in existing_strikes.data}

        strikes_logged = 0

        for habit in habits:
            habit_id = habit["id"]
            habit_title = habit["title"]
            deadline_time_str = habit.get("deadline_time")
            completed = habit.get("completed", False)

            # Skip if no deadline set
            if not deadline_time_str:
                continue

            # Parse deadline time
            deadline_time = datetime.strptime(deadline_time_str, "%H:%M:%S").time()

            # Check if deadline has passed
            if current_time < deadline_time:
                continue

            # Skip if already completed
            if completed:
                continue

            # Skip if we haven't sent a deadline reminder yet
            if habit_id not in reminded_habit_ids:
                continue

            # Skip if we already logged a strike today
            if habit_id in already_striked_ids:
                continue

            # Log the strike
            logger.info(f"[SCHEDULER] Logging strike for missed deadline: {habit_title}")

            try:
                habit_service.log_strike(
                    habit_id=habit_id,
                    reason="missed_deadline",
                    notes=f"Deadline {deadline_time_str} missed on {today}"
                )
                strikes_logged += 1
                logger.info(f"[SCHEDULER] Strike logged for habit_id={habit_id} ({habit_title})")

                # Optionally send a strike notification
                message = f"❌ STRIKE: {habit_title}\n\nYou missed the deadline. Strike logged."
                send_whatsapp_message(message)

            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to log strike for habit_id={habit_id}: {e}")

        if strikes_logged > 0:
            logger.info(f"[SCHEDULER] Logged {strikes_logged} strike(s) for missed deadlines")
        else:
            logger.info("[SCHEDULER] No missed deadlines found")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in check_missed_deadlines: {e}", exc_info=True)


def check_all():
    """
    Combined check for reminders and missed deadlines
    Runs both checks together every 10 seconds
    """
    check_and_send_reminders()
    check_missed_deadlines()


def start_scheduler():
    """
    Start the background scheduler
    Runs checks every 10 seconds
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already running")
        return

    scheduler = BackgroundScheduler()

    # Run both checks every 10 seconds
    scheduler.add_job(
        func=check_all,
        trigger=IntervalTrigger(seconds=10),
        id='habit_check',
        name='Check reminders and missed deadlines',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started - checking every 10 seconds")


def stop_scheduler():
    """Stop the background scheduler"""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
