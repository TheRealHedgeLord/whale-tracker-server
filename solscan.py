from http_client import Client


class SolScanAPI(Client):
    url = "https://pro-api.solscan.io"

    def __init__(self, api_token: str) -> None:
        self._api_token = api_token

    @property
    def headers(self) -> dict:
        return {"token": self._api_token}

    async def get_transactions_for_account(
        self, account: str, after_hash: str | None = None, limit: int = 10
    ) -> list:
        transactions = []
        before_hash = None
        reached_after_hash = False
        while True:
            params = {"account": account, "limit": limit}
            if before_hash:
                params["beforeHash"] = before_hash
            response = await self.call(
                "get",
                "/v1.0/account/transactions",
                params=params,
                headers=self.headers,
            )
            for transaction in response:
                transaction_hash = transaction["txHash"]
                if transaction_hash == after_hash:
                    reached_after_hash = True
                    break
                elif (
                    transaction_hash not in transactions
                    and transaction["status"] == "Success"
                ):
                    transactions.append(transaction_hash)
            if (
                not after_hash
                or reached_after_hash
                or len(response) == 0
                or (len(response) == 1 and response[-1]["txHash"] == before_hash)
            ):
                break
            before_hash = response[-1]["txHash"]
        return transactions

    async def get_raw_transaction_details(self, transaction_hash: str) -> dict:
        return await self.call(
            "get",
            f"/v1.0/transaction/{transaction_hash}",
            headers=self.headers,
        )  # type: ignore

    async def get_transaction_details(
        self, transaction_hash: str
    ) -> tuple[list, list, int, set]:
        response = await self.call(
            "get",
            f"/v1.0/transaction/{transaction_hash}",
            headers=self.headers,
        )
        instructions = set()
        for inner_instruction in response["innerInstructions"]:  # type: ignore
            for instruction in inner_instruction["parsedInstructions"]:
                instructions.add(instruction["programId"])
        return (
            response["tokenBalances"] if "tokenBalances" in response else [],  # type: ignore
            response["inputAccount"] if "inputAccount" in response else [],  # type: ignore
            response["blockTime"],  # type: ignore
            instructions,
        )

    async def get_transaction_actions(self, transaction_hash: str) -> dict:
        return await self.call(
            "get",
            "/v2.0/transaction/actions",
            params={"tx": transaction_hash},
            headers=self.headers,
        )  # type: ignore
