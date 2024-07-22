import os
import sys
import asyncio

from dotenv import load_dotenv
from pathlib import Path

from state_manager import State, TrackedWallet
from svm import Solana, Transaction
from telegram import TelegramBot, generate_transaction_message, SEPARATOR

load_dotenv()

SOLANA_RPC_HTTP_URL = os.environ["SOLANA_RPC_HTTP_URL"]
SOLSCAN_API_TOKEN = os.environ["SOLSCAN_API_V1"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WHALE_TRACKER_CHAT_ID = os.environ["WHALE_TRACKER_CHAT_ID"]

solana = Solana(SOLANA_RPC_HTTP_URL, SOLSCAN_API_TOKEN)
bot = TelegramBot(TELEGRAM_BOT_TOKEN)
state = State(f"{Path(__file__).parent}/.state")


def _get_message_and_timestamp(
    wallet: TrackedWallet, transaction: Transaction
) -> tuple[str, int]:
    message = generate_transaction_message(wallet["group"], wallet["name"], transaction)
    return message, transaction["block_time"]


async def _track_one_wallet(
    address: str, wallet: TrackedWallet
) -> tuple[tuple[str, str], list[tuple[str, int]]] | None:
    if not wallet["last_updated_hash"]:
        transactions = await solana.get_transactions(address)
        transactions = [transactions[-1]]
    else:
        transactions = await solana.get_transactions(
            address, after_hash=wallet["last_updated_hash"]
        )
    if len(transactions) > 0:
        return (address, transactions[-1]["transaction_hash"]), [
            _get_message_and_timestamp(wallet, transaction)
            for transaction in transactions
        ]


class CLI:
    @staticmethod
    async def track_wallets() -> None:
        all_wallets = state.get_all_tracked_wallets()
        tracked_data = await asyncio.gather(
            *[_track_one_wallet(wallet, all_wallets[wallet]) for wallet in all_wallets]
        )
        non_empty_data = [
            wallet_data for wallet_data in tracked_data if wallet_data is not None
        ]
        message_stream = []
        for _, message_and_timestamp in non_empty_data:
            message_stream += message_and_timestamp
        sorted_messages = [
            message
            for message, _ in sorted(
                message_stream,
                key=lambda message_and_timestamp: message_and_timestamp[1],
            )
        ]
        if len(sorted_messages) > 0:
            summary_message = SEPARATOR.join(sorted_messages)
            await bot.send_message(WHALE_TRACKER_CHAT_ID, summary_message)
        for (address, last_updated_hash), _ in non_empty_data:
            state.update_tracked_wallet(address, last_updated_hash=last_updated_hash)


if __name__ == "__main__":
    method = sys.argv[1]
    asyncio.run(getattr(CLI, method)())
