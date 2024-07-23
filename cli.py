import os
import sys
import asyncio

from dotenv import load_dotenv
from pathlib import Path
from pprint import pprint

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


def _get_ignored_wallets(
    address: str, wallet: TrackedWallet, all_wallets: dict[str, TrackedWallet]
) -> list[str]:
    ignored_wallets = []
    for account in all_wallets:
        if account != address and wallet["group"] == all_wallets[account]["group"]:
            ignored_wallets.append(account)
    return ignored_wallets


async def _track_one_wallet(
    address: str, wallet: TrackedWallet, all_wallets: dict[str, TrackedWallet]
) -> tuple[tuple[str, str], list[tuple[str, int]]] | None:
    ignored_wallets = _get_ignored_wallets(address, wallet, all_wallets)
    if not wallet["last_updated_hash"]:
        transactions = await solana.get_transactions(
            address, ignore_internal_transfers=ignored_wallets
        )
        transactions = [transactions[-1]]
    else:
        transactions = await solana.get_transactions(
            address,
            after_hash=wallet["last_updated_hash"],
            ignore_internal_transfers=ignored_wallets,
        )
    if len(transactions) > 0:
        if wallet["group"] not in CLI.lifespan_globals["mentioned_tokens_by_group"]:
            CLI.lifespan_globals["mentioned_tokens_by_group"][wallet["group"]] = []
        for transaction in transactions:
            for token_action in transaction["token_actions"]:
                token = (
                    token_action["token"] if token_action["token"] != "SOL" else None
                )
                if (
                    token
                    and token
                    not in CLI.lifespan_globals["mentioned_tokens_by_group"][
                        wallet["group"]
                    ]
                ):
                    CLI.lifespan_globals["mentioned_tokens_by_group"][
                        wallet["group"]
                    ].append(token)
        return (address, transactions[-1]["transaction_hash"]), [
            _get_message_and_timestamp(wallet, transaction)
            for transaction in transactions
        ]


class CLI:
    lifespan_globals = {}

    @staticmethod
    async def track_wallets() -> None:
        CLI.lifespan_globals["mentioned_tokens_by_group"] = {}
        all_wallets = state.get_all_tracked_wallets()
        tracked_data = await asyncio.gather(
            *[
                _track_one_wallet(wallet, all_wallets[wallet], all_wallets)
                for wallet in all_wallets
            ]
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
            print(summary_message)
            pprint(CLI.lifespan_globals["mentioned_tokens_by_group"])
            # await bot.send_message(WHALE_TRACKER_CHAT_ID, summary_message)
        # for (address, last_updated_hash), _ in non_empty_data:
        #     state.update_tracked_wallet(address, last_updated_hash=last_updated_hash)

    @staticmethod
    async def get_transaction_details(transaction_hash) -> None:
        response = await solana.solscan_api.get_transaction_details(transaction_hash)
        pprint(response)

    @staticmethod
    async def interpret_transaction(
        transaction_hash: str, owner: str, *ignored_internal_addresses
    ) -> None:
        response = await solana.interpret_transaction(
            transaction_hash,
            owner,
            ignore_internal_transfers=list(ignored_internal_addresses),
        )
        pprint(response)

    @staticmethod
    async def get_associated_token_account(mint: str, owner: str) -> None:
        account = solana.get_associated_token_account(mint, owner)
        print(account)


if __name__ == "__main__":
    method = sys.argv[1]
    args = sys.argv[2::]
    asyncio.run(getattr(CLI, method)(*args))
