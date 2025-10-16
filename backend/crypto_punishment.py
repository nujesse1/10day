"""
Crypto Punishment Module - Automated USDC transfers on Base network
Sends punishment payments from a dedicated wallet to a recipient address
"""
import os
import logging
from typing import Dict, Any
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Base Network Configuration
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")

# Auto-detect testnet vs mainnet
if "sepolia" in BASE_RPC_URL.lower():
    # Base Sepolia Testnet
    BASE_CHAIN_ID = 84532
    USDC_CONTRACT_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"  # USDC on Base Sepolia
    logger.info("Using Base Sepolia TESTNET")
else:
    # Base Mainnet
    BASE_CHAIN_ID = 8453
    USDC_CONTRACT_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # Native USDC on Base
    logger.info("Using Base MAINNET")

USDC_DECIMALS = 6  # USDC uses 6 decimals, not 18

# Wallet Configuration
PUNISHMENT_WALLET_PRIVATE_KEY = os.getenv("PUNISHMENT_WALLET_PRIVATE_KEY")
PUNISHMENT_RECEIVING_ADDRESS = os.getenv("PUNISHMENT_RECEIVING_ADDRESS")

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
        # Validate configuration
        if not PUNISHMENT_WALLET_PRIVATE_KEY:
            raise ValueError("PUNISHMENT_WALLET_PRIVATE_KEY not set in .env")

        # Use provided recipient or default from env
        recipient = recipient_address or PUNISHMENT_RECEIVING_ADDRESS
        if not recipient:
            raise ValueError("PUNISHMENT_RECEIVING_ADDRESS not set in .env")

        logger.info(f"[CRYPTO PUNISHMENT] Initiating ${amount_usd} USDC transfer to {recipient[:10]}...")

        # Connect to Base network
        w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

        if not w3.is_connected():
            raise ConnectionError(f"Failed to connect to Base network at {BASE_RPC_URL}")

        logger.info(f"[CRYPTO PUNISHMENT] Connected to Base network (Chain ID: {w3.eth.chain_id})")

        # Load account from private key
        account = w3.eth.account.from_key(PUNISHMENT_WALLET_PRIVATE_KEY)
        sender_address = account.address
        logger.info(f"[CRYPTO PUNISHMENT] Sender address: {sender_address}")

        # Load USDC contract
        usdc_contract = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS),
            abi=ERC20_ABI
        )

        # Convert USD amount to USDC units (multiply by 10^6 since USDC has 6 decimals)
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

        # Build transfer transaction
        nonce = w3.eth.get_transaction_count(sender_address)

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

        # Build transaction
        transaction = transfer_function.build_transaction({
            'chainId': BASE_CHAIN_ID,
            'gas': gas_estimate + 10000,  # Add buffer
            'gasPrice': gas_price,
            'nonce': nonce,
            'from': sender_address
        })

        logger.info(f"[CRYPTO PUNISHMENT] Transaction built. Signing...")

        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, PUNISHMENT_WALLET_PRIVATE_KEY)

        # Send transaction
        logger.info(f"[CRYPTO PUNISHMENT] Sending transaction...")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        logger.info(f"[CRYPTO PUNISHMENT] Transaction sent! Hash: {tx_hash_hex}")

        # Generate BaseScan link (testnet vs mainnet)
        if BASE_CHAIN_ID == 84532:  # Sepolia testnet
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
                message = f"${amount_usd} USDC sent successfully"
            else:
                logger.error(f"[CRYPTO PUNISHMENT] Transaction failed!")
                success = False
                message = "Transaction was sent but failed on-chain"
        except Exception as e:
            logger.warning(f"[CRYPTO PUNISHMENT] Could not wait for receipt: {e}")
            success = True  # Transaction was sent, just couldn't confirm
            message = f"${amount_usd} USDC transaction sent (confirmation pending)"

        return {
            "success": success,
            "message": message,
            "amount_usd": amount_usd,
            "tx_hash": tx_hash_hex,
            "basescan_link": basescan_link,
            "sender": sender_address,
            "recipient": recipient,
            "chain": "Base",
            "chain_id": BASE_CHAIN_ID
        }

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
