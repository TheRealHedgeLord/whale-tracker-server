import json
import asyncio

from solders.pubkey import Pubkey  # type: ignore
from typing import TypedDict, Literal, Any
from decimal import Decimal
from functools import cache

from http_client import Client
from solscan import SolScanAPI

SOL = "So11111111111111111111111111111111111111112"
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)
DUST = Decimal("0.01")


class SPL(TypedDict):
    ticker: str
    name: str
    mint: str
    decimals: int


class TokenAction(TypedDict):
    token: Literal["SOL"] | SPL
    amount: Decimal


class Transaction(TypedDict):
    transaction_hash: str
    token_actions: list[TokenAction]
    block_time: int


class RPC(Client):
    _version = "2.0"

    def __init__(self, rpc_url: str) -> None:
        self.url = rpc_url
        self._current_id = 1

    async def http_method(self, method: str, *params: Any) -> dict:
        data = json.dumps(
            {
                "jsonrpc": self._version,
                "id": self._current_id,
                "method": method,
                "params": list(params),
            }
        )
        self._current_id += 1
        return await self.call(
            "post",
            "",
            data=data,
            headers={"Content-Type": "application/json"},
        )  # type: ignore


class Solana:
    def __init__(self, rpc_url: str, solscan_api_token: str) -> None:
        self.rpc = RPC(rpc_url)
        self.solscan_api = SolScanAPI(solscan_api_token)

    @cache
    def get_associated_token_account(self, mint: str, owner: str) -> str:
        key, _ = Pubkey.find_program_address(
            seeds=[
                bytes(Pubkey.from_string(owner)),
                bytes(TOKEN_PROGRAM_ID),
                bytes(Pubkey.from_string(mint)),
            ],
            program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
        )
        return str(key)

    async def get_spl_balance(self, account: str, token: SPL) -> Decimal:
        mint = token["mint"]
        decimals = token["decimals"]
        token_account = self.get_associated_token_account(mint, account)
        response = await self.rpc.http_method(
            "getAccountInfo", token_account, {"encoding": "jsonParsed"}
        )
        if response["result"]["value"] is None:
            return Decimal("0")
        else:
            balance = response["result"]["value"]["data"]["parsed"]["info"][
                "tokenAmount"
            ]["amount"]
            return Decimal(balance) / Decimal(10**decimals)

    async def get_transactions(
        self,
        account: str,
        after_hash: str | None = None,
        limit: int = 10,
        ignore_internal_transfers: list[str] | None = None,
    ) -> list[Transaction]:
        trasnaction_hashes = await self.solscan_api.get_transactions_for_account(
            account, after_hash=after_hash, limit=limit
        )
        interpreted_transactions = await asyncio.gather(
            *[
                self.interpret_transaction(
                    transaction_hash,
                    account,
                    ignore_internal_transfers=ignore_internal_transfers,
                )
                for transaction_hash in trasnaction_hashes
            ]
        )
        return [
            transaction
            for transaction in sorted(
                interpreted_transactions, key=lambda tx: tx["block_time"]
            )
            if len(transaction["token_actions"]) > 0
        ]

    async def interpret_transaction(
        self,
        transaction_hash: str,
        owner: str,
        ignore_internal_transfers: list[str] | None = None,
    ) -> Transaction:
        token_actions = []
        token_balances, input_accounts, block_time = (
            await self.solscan_api.get_transaction_details(transaction_hash)
        )
        token_balance_changes = {}
        token_metas = {}
        for token in token_balances:
            owner_token_account = self.get_associated_token_account(
                token["token"]["tokenAddress"], owner
            )
            internal_token_accounts = (
                [
                    self.get_associated_token_account(
                        token["token"]["tokenAddress"], address
                    )
                    for address in ignore_internal_transfers
                ]
                if ignore_internal_transfers
                else []
            )
            if (
                owner_token_account == token["account"]
                or token["account"] in internal_token_accounts
            ):
                mint = token["token"]["tokenAddress"]
                decimals = token["token"]["decimals"]
                if mint not in token_balance_changes:
                    token_balance_changes[mint] = Decimal("0")
                if mint not in token_metas:
                    token_metas[mint] = {
                        "ticker": token["token"]["symbol"],
                        "name": token["token"]["name"],
                        "mint": mint,
                        "decimals": decimals,
                    }
                token_balance_changes[mint] += (
                    Decimal(token["amount"]["postAmount"])
                    - Decimal(token["amount"]["preAmount"])
                ) / Decimal(10**decimals)
        for mint in token_balance_changes:
            if (
                token_balance_changes[mint] > DUST
                or token_balance_changes[mint] < -DUST
            ):
                token_actions.append(
                    {"token": token_metas[mint], "amount": token_balance_changes[mint]}
                )
        sol_diff = Decimal("0")
        all_relevant_accounts = (
            [owner] + ignore_internal_transfers
            if ignore_internal_transfers
            else [owner]
        )
        for account_diff in input_accounts:
            if account_diff["account"] in all_relevant_accounts:
                sol_diff += Decimal(
                    account_diff["postBalance"] - account_diff["preBalance"]
                ) / Decimal(10**9)
        if sol_diff > DUST or sol_diff < -DUST:
            token_actions.append({"token": "SOL", "amount": sol_diff})
        return {
            "transaction_hash": transaction_hash,
            "token_actions": token_actions,
            "block_time": block_time,
        }
