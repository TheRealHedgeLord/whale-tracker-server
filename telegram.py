from datetime import datetime
from typing import Any
from decimal import Decimal

from http_client import Client
from svm import Transaction, TokenAction

SEPARATOR = "\n------------------------------------\n"


def _parse_token_action(token_action: TokenAction) -> str:
    identifier = (
        "<b>SOL</b>"
        if token_action["token"] == "SOL"
        else f"<b>{token_action['token']['ticker']}</b>"
    )
    positive_sign = "+" if token_action["amount"] > Decimal("0") else ""
    return f"<b>{positive_sign}{token_action['amount']}</b> {identifier}"


def generate_transaction_message(
    group: str, name: str, transaction: Transaction
) -> str:
    time = datetime.fromtimestamp(transaction["block_time"])
    transaction_hash = transaction["transaction_hash"]
    message = (
        f"{time.astimezone()}:\n"
        f"<b>{group} ({name})</b>\n\n"
        + "\n".join(
            [_parse_token_action(token) for token in transaction["token_actions"]]
        )
        + f'\n\n<a href="https://solscan.io/tx/{transaction_hash}"><u>View Transaction</u></a>'
    )
    return message


class TelegramBot(Client):
    url = "https://api.telegram.org"

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token

    async def send_message(self, chat_id: str, message: str) -> Any:
        return await self.call(
            "get",
            f"/bot{self._bot_token}/sendMessage",
            params={"chat_id": chat_id, "parse_mode": "html", "text": message},
        )
