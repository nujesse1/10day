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
                strike_result = habit_service.log_strike(
                    habit_id=habit_id,
                    reason="missed_deadline",
                    notes=f"Deadline {deadline_time_str} missed on {today}"
                )
                strikes_logged += 1
                logger.info(f"[SCHEDULER] Strike logged for habit_id={habit_id} ({habit_title})")

                # Send strike notification with punishment info
                strike_count = strike_result.get("strike_count", 0)
                punishment_info = strike_result.get("punishment", {})

                if punishment_info.get("status") == "success":
                    # Punishment habit assigned (Strike 1)
                    punishment_title = punishment_info.get("punishment", "Unknown")
                    message = f"❌ STRIKE {strike_count}: {habit_title}\n\nYou missed the deadline. Strike logged.\n\n⚡ PUNISHMENT ASSIGNED: {punishment_title}\n\nComplete it by 11:59 PM or face the consequences."
                elif punishment_info.get("status") == "crypto_success":
                    # Crypto punishment executed (Strike 2)
                    amount = punishment_info.get("amount_usd", 10)
                    tx_hash = punishment_info.get("tx_hash", "Unknown")
                    basescan_link = punishment_info.get("basescan_link", "")
                    message = f"❌ STRIKE {strike_count}: {habit_title}\n\nYou missed the deadline. Strike logged.\n\n💸 CRYPTO PUNISHMENT EXECUTED 💸\n\n${amount} USDC has been sent from your wallet.\n\nTransaction: {tx_hash[:16]}...\n\nView on BaseScan:\n{basescan_link}\n\nTHE MONEY IS GONE. NO TAKE-BACKS.\n\n(Testing mode: $1 only)"
                elif punishment_info.get("status") == "crypto_error":
                    # Crypto punishment failed (Strike 2)
                    error_msg = punishment_info.get("error", "Unknown error")
                    message = f"❌ STRIKE {strike_count}: {habit_title}\n\nYou missed the deadline. Strike logged.\n\n⚠️ CRYPTO PUNISHMENT FAILED ⚠️\n\nAttempted to send $10 USDC but failed:\n{error_msg}\n\nFix your wallet setup immediately."
                elif punishment_info.get("status") == "placeholder":
                    # Placeholder strike (3-4)
                    placeholder_msg = punishment_info.get("message", "Punishment not yet implemented")
                    message = f"❌ STRIKE {strike_count}: {habit_title}\n\nYou missed the deadline. {placeholder_msg}"
                else:
                    # Fallback
                    message = f"❌ STRIKE {strike_count}: {habit_title}\n\nYou missed the deadline. Strike logged."

                send_whatsapp_message(message)

            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to log strike for habit_id={habit_id}: {e}")

        if strikes_logged > 0:
            logger.info(f"[SCHEDULER] Logged {strikes_logged} strike(s) for missed deadlines")
        else:
            logger.info("[SCHEDULER] No missed deadlines found")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in check_missed_deadlines: {e}", exc_info=True)


def cleanup_punishment_habits():
    """
    Delete punishment habits that have expired (auto_delete_at <= today)
    Called once daily at 11:59 PM, but also catches up on missed cleanups
    if server was down
    """
    try:
        from datetime import date

        logger.info("[SCHEDULER] Cleaning up expired punishment habits...")

        today = date.today()

        # Find all habits where auto_delete_at <= today (includes past dates)
        # This ensures we clean up even if server was down
        expired_habits = habit_service.supabase.table("habits")\
            .select("*")\
            .eq("punishment_habit", True)\
            .lte("auto_delete_at", str(today))\
            .execute()

        if not expired_habits.data:
            logger.info("[SCHEDULER] No expired punishment habits to clean up")
            return

        logger.info(f"[SCHEDULER] Found {len(expired_habits.data)} expired punishment habit(s)")

        # Delete each expired habit
        for habit in expired_habits.data:
            habit_id = habit["id"]
            habit_title = habit["title"]
            auto_delete_at = habit.get("auto_delete_at")

            try:
                habit_service.supabase.table("habits")\
                    .delete()\
                    .eq("id", habit_id)\
                    .execute()

                logger.info(f"[SCHEDULER] Deleted punishment habit: {habit_title} (ID: {habit_id}, expired: {auto_delete_at})")

            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to delete habit {habit_id}: {e}")

        logger.info("[SCHEDULER] Punishment habit cleanup completed")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in cleanup_punishment_habits: {e}", exc_info=True)


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

    # Run punishment cleanup daily at 11:59 PM
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(
        func=cleanup_punishment_habits,
        trigger=CronTrigger(hour=23, minute=59),
        id='punishment_cleanup',
        name='Cleanup expired punishment habits',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started - checking every 10 seconds, cleanup at 11:59 PM")


def stop_scheduler():
    """Stop the background scheduler"""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
