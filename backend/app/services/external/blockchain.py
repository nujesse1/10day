"""
Crypto Punishment Module - Automated USDC transfers on Base network
Sends punishment payments from a dedicated wallet to a recipient address
"""
import logging
from typing import Dict, Any
from web3 import Web3
from app.core.config import settings
from app.core.constants import (
    USDC_DECIMALS,
    BASE_SEPOLIA_CHAIN_ID,
    BASE_MAINNET_CHAIN_ID,
    USDC_CONTRACT_BASE_SEPOLIA,
    USDC_CONTRACT_BASE_MAINNET
)

logger = logging.getLogger(__name__)

# Base Network Configuration
BASE_RPC_URL = settings.BASE_RPC_URL or "https://mainnet.base.org"

# Auto-detect testnet vs mainnet
if "sepolia" in BASE_RPC_URL.lower():
    # Base Sepolia Testnet
    BASE_CHAIN_ID = BASE_SEPOLIA_CHAIN_ID
    USDC_CONTRACT_ADDRESS = USDC_CONTRACT_BASE_SEPOLIA
    logger.info("Using Base Sepolia TESTNET")
else:
    # Base Mainnet
    BASE_CHAIN_ID = BASE_MAINNET_CHAIN_ID
    USDC_CONTRACT_ADDRESS = USDC_CONTRACT_BASE_MAINNET
    logger.info("Using Base MAINNET")

# Wallet Configuration
PUNISHMENT_WALLET_PRIVATE_KEY = settings.PUNISHMENT_WALLET_PRIVATE_KEY
PUNISHMENT_RECEIVING_ADDRESS = settings.PUNISHMENT_RECEIVING_ADDRESS

# Minimal ERC-20 ABI - Only need transfer and balanceOf functions
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]


def _validate_crypto_config(recipient_address: str = None) -> str:
    """
    Validate crypto configuration and return recipient address

    Args:
        recipient_address: Override default recipient

    Returns:
        Validated recipient address

    Raises:
        ValueError: If configuration is invalid
    """
    if not PUNISHMENT_WALLET_PRIVATE_KEY:
        raise ValueError("PUNISHMENT_WALLET_PRIVATE_KEY not set in .env")

    # Use provided recipient or default from env
    recipient = recipient_address or PUNISHMENT_RECEIVING_ADDRESS
    if not recipient:
        raise ValueError("PUNISHMENT_RECEIVING_ADDRESS not set in .env")

    logger.info(f"[CRYPTO PUNISHMENT] Initiating USDC transfer to {recipient[:10]}...")
    return recipient


def _connect_to_base_network():
    """
    Connect to Base network and load account

    Returns:
        Tuple of (web3_instance, account, usdc_contract)

    Raises:
        ConnectionError: If connection fails
    """
    # Connect to Base network
    w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to Base network at {BASE_RPC_URL}")

    logger.info(f"[CRYPTO PUNISHMENT] Connected to Base network (Chain ID: {w3.eth.chain_id})")

    # Load account from private key
    account = w3.eth.account.from_key(PUNISHMENT_WALLET_PRIVATE_KEY)
    logger.info(f"[CRYPTO PUNISHMENT] Sender address: {account.address}")

    # Load USDC contract
    usdc_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS),
        abi=ERC20_ABI
    )

    return w3, account, usdc_contract


def _check_balances(w3, account, usdc_contract, amount_usd: float):
    """
    Check USDC and ETH balances are sufficient

    Args:
        w3: Web3 instance
        account: Account object
        usdc_contract: USDC contract instance
        amount_usd: Amount to send in USD

    Raises:
        ValueError: If balances are insufficient
    """
    sender_address = account.address

    # Convert USD amount to USDC units
    usdc_amount = int(amount_usd * (10 ** USDC_DECIMALS))
    logger.info(f"[CRYPTO PUNISHMENT] Sending {usdc_amount} USDC units (${amount_usd})")

    # Check USDC balance
    balance = usdc_contract.functions.balanceOf(sender_address).call()
    balance_usd = balance / (10 ** USDC_DECIMALS)
    logger.info(f"[CRYPTO PUNISHMENT] Wallet balance: {balance} USDC units (${balance_usd:.2f})")

    if balance < usdc_amount:
        raise ValueError(
            f"Insufficient USDC balance. Have ${balance_usd:.2f}, need ${amount_usd:.2f}. "
            f"Please fund the punishment wallet at {sender_address}"
        )

    # Check ETH balance for gas
    eth_balance = w3.eth.get_balance(sender_address)
    eth_balance_readable = w3.from_wei(eth_balance, 'ether')
    logger.info(f"[CRYPTO PUNISHMENT] ETH balance for gas: {eth_balance_readable} ETH")

    if eth_balance == 0:
        raise ValueError(
            f"No ETH for gas fees. Please send ~0.001 ETH to {sender_address}"
        )


def _build_usdc_transfer_tx(w3, account, usdc_contract, recipient: str, amount_usd: float) -> dict:
    """
    Build USDC transfer transaction

    Args:
        w3: Web3 instance
        account: Account object
        usdc_contract: USDC contract instance
        recipient: Recipient address
        amount_usd: Amount to send in USD

    Returns:
        Built transaction dict ready for signing
    """
    sender_address = account.address
    usdc_amount = int(amount_usd * (10 ** USDC_DECIMALS))

    # Build the transfer function call
    transfer_function = usdc_contract.functions.transfer(
        Web3.to_checksum_address(recipient),
        usdc_amount
    )

    # Estimate gas
    try:
        gas_estimate = transfer_function.estimate_gas({'from': sender_address})
        logger.info(f"[CRYPTO PUNISHMENT] Estimated gas: {gas_estimate}")
    except Exception as e:
        logger.warning(f"[CRYPTO PUNISHMENT] Gas estimation failed: {e}. Using default.")
        gas_estimate = 100000  # Fallback gas limit

    # Get current gas price
    gas_price = w3.eth.gas_price
    logger.info(f"[CRYPTO PUNISHMENT] Gas price: {w3.from_wei(gas_price, 'gwei')} gwei")

    # Get nonce
    nonce = w3.eth.get_transaction_count(sender_address)

    # Build transaction
    transaction = transfer_function.build_transaction({
        'chainId': BASE_CHAIN_ID,
        'gas': gas_estimate + 10000,  # Add buffer
        'gasPrice': gas_price,
        'nonce': nonce,
        'from': sender_address
    })

    logger.info(f"[CRYPTO PUNISHMENT] Transaction built successfully")
    return transaction


def _send_and_confirm_tx(w3, account, transaction):
    """
    Sign, send, and confirm transaction

    Args:
        w3: Web3 instance
        account: Account object
        transaction: Built transaction dict

    Returns:
        Tuple of (tx_hash_hex, success, message, basescan_link)
    """
    # Sign transaction
    logger.info(f"[CRYPTO PUNISHMENT] Signing transaction...")
    signed_txn = w3.eth.account.sign_transaction(transaction, PUNISHMENT_WALLET_PRIVATE_KEY)

    # Send transaction
    logger.info(f"[CRYPTO PUNISHMENT] Sending transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    tx_hash_hex = tx_hash.hex()

    logger.info(f"[CRYPTO PUNISHMENT] Transaction sent! Hash: {tx_hash_hex}")

    # Generate BaseScan link (testnet vs mainnet)
    if BASE_CHAIN_ID == BASE_SEPOLIA_CHAIN_ID:  # Sepolia testnet
        basescan_link = f"https://sepolia.basescan.org/tx/{tx_hash_hex}"
    else:  # Mainnet
        basescan_link = f"https://basescan.org/tx/{tx_hash_hex}"

    logger.info(f"[CRYPTO PUNISHMENT] View on BaseScan: {basescan_link}")

    # Wait for receipt (with timeout)
    try:
        logger.info(f"[CRYPTO PUNISHMENT] Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            logger.info(f"[CRYPTO PUNISHMENT] Transaction confirmed! Block: {receipt['blockNumber']}")
            success = True
            message = "USDC sent successfully"
        else:
            logger.error(f"[CRYPTO PUNISHMENT] Transaction failed!")
            success = False
            message = "Transaction was sent but failed on-chain"
    except Exception as e:
        logger.warning(f"[CRYPTO PUNISHMENT] Could not wait for receipt: {e}")
        success = True  # Transaction was sent, just couldn't confirm
        message = "USDC transaction sent (confirmation pending)"

    return tx_hash_hex, success, message, basescan_link


def _format_punishment_response(tx_hash: str, success: bool, message: str, basescan_link: str,
                                amount_usd: float, sender: str, recipient: str) -> Dict[str, Any]:
    """
    Format the punishment response dict

    Args:
        tx_hash: Transaction hash
        success: Whether transaction succeeded
        message: Success/failure message
        basescan_link: BaseScan URL
        amount_usd: Amount sent in USD
        sender: Sender address
        recipient: Recipient address

    Returns:
        Formatted response dict
    """
    return {
        "success": success,
        "message": f"${amount_usd} {message}",
        "amount_usd": amount_usd,
        "tx_hash": tx_hash,
        "basescan_link": basescan_link,
        "sender": sender,
        "recipient": recipient,
        "chain": "Base",
        "chain_id": BASE_CHAIN_ID
    }


def send_usdc_punishment(amount_usd: float, recipient_address: str = None) -> Dict[str, Any]:
    """
    Send USDC on Base network as punishment for missed habits

    Args:
        amount_usd: Amount in USD to send (e.g., 10.0 for $10)
        recipient_address: Override default recipient (for testing)

    Returns:
        Dict with success status, transaction hash, and BaseScan link
    """
    try:
        # Step 1: Validate configuration
        recipient = _validate_crypto_config(recipient_address)

        # Step 2: Connect to Base network and load account
        w3, account, usdc_contract = _connect_to_base_network()

        # Step 3: Check balances
        _check_balances(w3, account, usdc_contract, amount_usd)

        # Step 4: Build transaction
        transaction = _build_usdc_transfer_tx(w3, account, usdc_contract, recipient, amount_usd)

        # Step 5: Send and confirm transaction
        tx_hash, success, message, basescan_link = _send_and_confirm_tx(w3, account, transaction)

        # Step 6: Format response
        return _format_punishment_response(
            tx_hash, success, message, basescan_link,
            amount_usd, account.address, recipient
        )

    except Exception as e:
        logger.error(f"[CRYPTO PUNISHMENT] Error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "amount_usd": amount_usd
        }


def check_punishment_wallet_balance() -> Dict[str, Any]:
    """
    Check the balance of the punishment wallet (USDC and ETH)

    Returns:
        Dict with USDC balance, ETH balance, and wallet address
    """
    try:
        if not PUNISHMENT_WALLET_PRIVATE_KEY:
            return {"error": "PUNISHMENT_WALLET_PRIVATE_KEY not set"}

        w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

        if not w3.is_connected():
            return {"error": f"Cannot connect to Base at {BASE_RPC_URL}"}

        account = w3.eth.account.from_key(PUNISHMENT_WALLET_PRIVATE_KEY)
        address = account.address

        # Check USDC balance
        usdc_contract = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS),
            abi=ERC20_ABI
        )
        usdc_balance_raw = usdc_contract.functions.balanceOf(address).call()
        usdc_balance = usdc_balance_raw / (10 ** USDC_DECIMALS)

        # Check ETH balance
        eth_balance_raw = w3.eth.get_balance(address)
        eth_balance = w3.from_wei(eth_balance_raw, 'ether')

        return {
            "success": True,
            "address": address,
            "usdc_balance": usdc_balance,
            "eth_balance": float(eth_balance),
            "chain": "Base"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
