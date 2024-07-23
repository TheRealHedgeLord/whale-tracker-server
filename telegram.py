from datetime import datetime
from typing import Any, TypedDict
from decimal import Decimal

from http_client import Client
from svm import Transaction, TokenAction

SEPARATOR = "\n------------------------------------\n"

HELP_TEXT = """<b>Welcome To Whale Tracker</b>

You can use command to call telegram methods to track your favourite whales!

<b>Schema</b>

The first line will be a telegram command with the name of the method, the following lines will be keyword arguments of the methods, with keys and values separated by ":", each keyword argument will be in a different line.

<b>Methods</b>

<b>help</b>()
 - get help text

<b>show_tracked_wallets</b>(group)
 - show all tracked wallets for group, if group is not passed, show all tracked wallets for all groups

<b>add_wallet</b>(address, name, group)
 - add a new wallet to track (admin only)

<b>update_wallet</b>(address, name, group)
 - updated tracked wallet, name and group are optional arguments (admin only)

<b>remove_wallet</b>(address)
 - remove a wallet from tracker (admin only)

<b>rename_group</b>(group, new_name)
 - rename a group (admin only)

"""


class TelegramMethod(TypedDict):
    user: str
    method: str
    kwargs: dict[str, str]
    update_id: int


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

    async def get_bot_commands(
        self, chat_id: str, after_id: int = 0
    ) -> list[TelegramMethod]:
        response = await self.call(
            "get",
            f"/bot{self._bot_token}/getUpdates",
        )
        highest_id = max([update["update_id"] for update in response["result"]])  # type: ignore
        telegram_methods = []
        relevant_updates = [
            update
            for update in response["result"]  # type: ignore
            if "message" in update
            and update["update_id"] > after_id
            and str(update["message"]["chat"]["id"]) == chat_id
            and "entities" in update["message"]
            and "bot_command"
            in [entity["type"] for entity in update["message"]["entities"]]
        ]
        for update in relevant_updates:
            lines = update["message"]["text"].split("\n")
            method = lines[0].strip()[1::]
            if " " not in method:
                kwargs = {}
                for line in lines[1::]:
                    key_and_value = line.split(":")
                    if len(key_and_value) == 2:
                        key = key_and_value[0].strip()
                        value = key_and_value[1].strip()
                        if " " not in key:
                            kwargs[key] = value
                telegram_methods.append(
                    {
                        "method": method,
                        "kwargs": kwargs,
                        "user": update["message"]["from"]["username"],
                        "update_id": update["update_id"],
                    }
                )
        return sorted(telegram_methods, key=lambda x: x["update_id"])

    async def send_message(self, chat_id: str, message: str) -> Any:
        return await self.call(
            "get",
            f"/bot{self._bot_token}/sendMessage",
            params={"chat_id": chat_id, "parse_mode": "html", "text": message},
        )
