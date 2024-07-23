import asyncio

from solders.pubkey import Pubkey  # type: ignore
from typing import TypedDict, Literal
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


class TokenAction(TypedDict):
    token: Literal["SOL"] | SPL
    amount: Decimal


class Transaction(TypedDict):
    transaction_hash: str
    token_actions: list[TokenAction]
    block_time: int


class RPC(Client):
    def __init__(self, rpc_url: str) -> None:
        self.url = rpc_url


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
        token_balances, sol_transfers, unknown_transfers, block_time = (
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
        for sol_transfer in sol_transfers:
            internal_accounts = (
                ignore_internal_transfers if ignore_internal_transfers else []
            )
            if (
                sol_transfer["source"] == owner
                and sol_transfer["destination"] not in internal_accounts
            ):
                sol_diff -= Decimal(sol_transfer["amount"]) / Decimal("1000000000")
            elif (
                sol_transfer["destination"] == owner
                and sol_transfer["source"] not in internal_accounts
            ):
                sol_diff += Decimal(sol_transfer["amount"]) / Decimal("1000000000")
        for unknown in unknown_transfers:
            if "event" in unknown:
                for event in unknown["event"]:
                    if (
                        "source" in event
                        and "destination" in event
                        and "amount" in event
                    ):
                        amount = Decimal(event["amount"]) / Decimal("1000000000")
                        if event["destination"] == self.get_associated_token_account(
                            SOL, owner
                        ):
                            sol_diff += amount
                        if event["source"] == self.get_associated_token_account(
                            SOL, owner
                        ):
                            sol_diff -= amount
        if sol_diff > DUST or sol_diff < -DUST:
            token_actions.append({"token": "SOL", "amount": sol_diff})
        return {
            "transaction_hash": transaction_hash,
            "token_actions": token_actions,
            "block_time": block_time,
        }
