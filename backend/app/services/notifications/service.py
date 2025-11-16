"""
Notifications Service - Message formatting and delivery
Centralizes all notification message templates and sending logic
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ============================================================================
# MESSAGE FORMATTING
# ============================================================================

def format_start_reminder(habit_title: str) -> str:
    """
    Format a reminder message for habit start time

    Args:
        habit_title: The habit title

    Returns:
        Formatted reminder message
    """
    return f"🔔 TIME TO START: {habit_title}\n\nGet moving! This habit is scheduled to start now."


def format_deadline_reminder(habit_title: str) -> str:
    """
    Format a reminder message for habit deadline

    Args:
        habit_title: The habit title

    Returns:
        Formatted reminder message
    """
    return f"⏰ DEADLINE APPROACHING: {habit_title}\n\nTime's up! Complete this habit now and send proof."


def format_strike_notification(
    habit_title: str,
    strike_count: int,
    punishment_result: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format a strike notification message with punishment details

    Args:
        habit_title: The habit that was missed
        strike_count: Total strike count for today
        punishment_result: Optional punishment result dict (from punishments.assign_punishment)

    Returns:
        Formatted strike notification message
    """
    base_message = f"⚠️ STRIKE LOGGED: {habit_title}\n\nStrike count for today: {strike_count}"

    if not punishment_result:
        return base_message

    status = punishment_result.get("status")

    if status == "success":
        # Punishment habit created (Strike 1)
        punishment_habit = punishment_result.get("punishment")
        return (
            f"{base_message}\n\n"
            f"⚡ PUNISHMENT ASSIGNED:\n{punishment_habit}\n\n"
            f"Complete this immediately or face further consequences."
        )

    elif status == "crypto_success":
        # Crypto payment sent (Strike 2)
        amount = punishment_result.get("amount_usd", 0)
        tx_hash = punishment_result.get("tx_hash", "")[:10]  # Truncate hash
        basescan_link = punishment_result.get("basescan_link", "")
        return (
            f"{base_message}\n\n"
            f"💸 FINANCIAL PUNISHMENT EXECUTED:\n"
            f"${amount} USDC has been sent from your wallet.\n\n"
            f"Transaction: {tx_hash}...\n"
            f"View on BaseScan: {basescan_link}\n\n"
            f"This is the cost of your failure."
        )

    elif status == "crypto_error":
        # Crypto payment failed
        error = punishment_result.get("error", "Unknown error")
        return (
            f"{base_message}\n\n"
            f"⚠️ CRYPTO PUNISHMENT FAILED:\n{error}\n\n"
            f"You got lucky this time, but fix the payment setup."
        )

    elif status == "placeholder":
        # Not implemented yet (Strike 3+)
        return (
            f"{base_message}\n\n"
            f"⚠️ Strike {strike_count} logged. Further punishments coming soon."
        )

    else:
        # Unknown status
        return base_message


# ============================================================================
# NOTIFICATION SENDING
# ============================================================================

class NotificationService:
    """
    Service for sending notifications via various channels
    """

    def __init__(self, send_callback=None):
        """
        Initialize notification service

        Args:
            send_callback: Optional callback function for sending messages
                          Should have signature: callback(message: str) -> bool
        """
        self.send_callback = send_callback

    def send_notification(self, message: str) -> bool:
        """
        Send a notification message

        Args:
            message: The message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.send_callback:
            logger.warning("No send callback configured - notification not sent")
            logger.info(f"Would have sent: {message}")
            return False

        try:
            result = self.send_callback(message)
            if result:
                logger.info("Notification sent successfully")
            else:
                logger.warning("Notification send callback returned False")
            return result
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def send_reminder(self, habit_title: str, reminder_type: str) -> bool:
        """
        Send a habit reminder

        Args:
            habit_title: The habit title
            reminder_type: 'start' or 'deadline'

        Returns:
            True if sent successfully, False otherwise
        """
        if reminder_type == "start":
            message = format_start_reminder(habit_title)
        elif reminder_type == "deadline":
            message = format_deadline_reminder(habit_title)
        else:
            logger.error(f"Unknown reminder type: {reminder_type}")
            return False

        return self.send_notification(message)

    def send_strike_notification(
        self,
        habit_title: str,
        strike_count: int,
        punishment_result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a strike notification with punishment details

        Args:
            habit_title: The habit that was missed
            strike_count: Total strike count for today
            punishment_result: Optional punishment result dict

        Returns:
            True if sent successfully, False otherwise
        """
        message = format_strike_notification(habit_title, strike_count, punishment_result)
        return self.send_notification(message)
