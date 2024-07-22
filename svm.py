import asyncio

from solders.pubkey import Pubkey  # type: ignore
from typing import TypedDict, Literal
from decimal import Decimal

from http_client import Client
from solscan import SolScanAPI


TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)
DUST_SOL = Decimal("0.01")


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
        self, account: str, after_hash: str | None = None, limit: int = 10
    ) -> list[Transaction]:
        trasnaction_hashes = await self.solscan_api.get_transactions_for_account(
            account, after_hash=after_hash, limit=limit
        )
        interpreted_transactions = await asyncio.gather(
            *[
                self._interpret_transaction(transaction_hash, account)
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

    async def _interpret_transaction(
        self, transaction_hash: str, owner: str
    ) -> Transaction:
        token_actions = []
        token_balances, sol_transfers, block_time = (
            await self.solscan_api.get_transaction_details(transaction_hash)
        )
        for token in token_balances:
            owner_token_account = self.get_associated_token_account(
                token["token"]["tokenAddress"], owner
            )
            if owner_token_account == token["account"]:
                decimals = token["token"]["decimals"]
                token_actions.append(
                    {
                        "token": {
                            "ticker": token["token"]["symbol"],
                            "name": token["token"]["name"],
                            "mint": token["token"]["tokenAddress"],
                        },
                        "amount": (
                            Decimal(token["amount"]["postAmount"])
                            - Decimal(token["amount"]["preAmount"])
                        )
                        / Decimal(10**decimals),
                    }
                )
        for sol_transfer in sol_transfers:
            sol_diff = Decimal("0")
            if sol_transfer["source"] == owner:
                sol_diff -= Decimal(sol_transfer["amount"]) / Decimal("1000000000")
            elif sol_transfer["destination"] == owner:
                sol_diff += Decimal(sol_transfer["amount"]) / Decimal("1000000000")
            if sol_diff > DUST_SOL or sol_diff < -DUST_SOL:
                token_actions.append({"token": "SOL", "amount": sol_diff})
        return {
            "transaction_hash": transaction_hash,
            "token_actions": token_actions,
            "block_time": block_time,
        }
