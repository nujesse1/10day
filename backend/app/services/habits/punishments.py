"""
Punishment assignment logic
Handles assigning punishments based on strike count
"""
import logging
from typing import Dict, Any

from app.core.constants import STRIKE_2_CRYPTO_AMOUNT_USD
from app.utils.timezone import get_pacific_today_date, get_pacific_current_time
from . import repository

logger = logging.getLogger(__name__)

# Import crypto punishment module
try:
    from app.services.external.blockchain import send_usdc_punishment
    CRYPTO_ENABLED = True
    logger.info("Crypto punishment module loaded successfully")
except ImportError as e:
    logger.warning(f"Crypto punishment module not available: {e}")
    CRYPTO_ENABLED = False


def assign_punishment(strike_count: int) -> Dict[str, Any]:
    """
    Assign a punishment habit based on today's total strike count

    Args:
        strike_count: Number of strikes accumulated today

    Returns:
        Dict with punishment details
    """
    # Use Pacific timezone for all time operations
    today = get_pacific_today_date()
    current_time = get_pacific_current_time()

    # Hard-coded punishment escalation rules
    if strike_count == 1:
        # Strike 1: Assign punishment habit
        punishment_title = "PUNISHMENT: 5K Run"
        start_time = current_time.strftime("%H:%M")
        deadline_time = "23:59"

        # Create the punishment habit using repository
        habit_data = repository.create_habit(
            title=punishment_title,
            start_time=start_time,
            deadline_time=deadline_time,
            punishment_habit=True,
            auto_delete_at=str(today)
        )

        return {
            "status": "success",
            "message": f"Punishment assigned: {punishment_title}",
            "strike_count": strike_count,
            "punishment": punishment_title,
            "data": habit_data
        }

    elif strike_count == 2:
        # Strike 2: CRYPTO PUNISHMENT - Send USDC on Base
        logger.info(f"[PUNISHMENT] Strike 2 triggered - executing crypto punishment")

        if not CRYPTO_ENABLED:
            logger.error("[PUNISHMENT] Crypto module not available!")
            return {
                "status": "error",
                "message": "Strike 2: Crypto punishment not available (module not loaded)",
                "strike_count": strike_count
            }

        # Execute the crypto transfer
        crypto_result = send_usdc_punishment(amount_usd=STRIKE_2_CRYPTO_AMOUNT_USD)

        if crypto_result.get("success"):
            logger.info(f"[PUNISHMENT] Crypto punishment successful: {crypto_result.get('tx_hash')}")
            return {
                "status": "crypto_success",
                "message": f"Strike {strike_count}: ${STRIKE_2_CRYPTO_AMOUNT_USD} USDC sent to punishment address",
                "strike_count": strike_count,
                "amount_usd": STRIKE_2_CRYPTO_AMOUNT_USD,
                "tx_hash": crypto_result.get("tx_hash"),
                "basescan_link": crypto_result.get("basescan_link"),
                "crypto_details": crypto_result
            }
        else:
            logger.error(f"[PUNISHMENT] Crypto punishment failed: {crypto_result.get('error')}")
            return {
                "status": "crypto_error",
                "message": f"Strike {strike_count}: Failed to send USDC - {crypto_result.get('error')}",
                "strike_count": strike_count,
                "error": crypto_result.get("error")
            }

    elif strike_count == 3:
        # Strike 3: Placeholder - just notify
        return {
            "status": "placeholder",
            "message": f"Strike {strike_count} logged. Punishment not yet implemented.",
            "strike_count": strike_count
        }

    else:  # strike_count >= 4
        # Strike 4+: Placeholder - just notify
        return {
            "status": "placeholder",
            "message": f"Strike {strike_count} logged. Punishment not yet implemented.",
            "strike_count": strike_count
        }
