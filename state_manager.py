import os
import json

from typing import TypedDict, Any


class TrackedWallet(TypedDict):
    name: str
    group: str
    last_updated_hash: str | None


class ServerParams(TypedDict):
    admin_users: list[str]
    last_processed_update_id: int


class State:
    def __init__(self, root: str) -> None:
        self._root = root

    def get_tracked_wallet(self, address: str) -> TrackedWallet: ...

    def update_tracked_wallet(self, address: str, **kwargs: Any):
        file_path = f"{self._root}/tracked_wallets/{address}.json"
        with open(file_path, mode="r") as f:
            wallet = json.load(f)
        wallet.update(kwargs)
        with open(file_path, mode="w") as f:
            json.dump(wallet, f)

    def get_all_tracked_wallets(self) -> dict[str, TrackedWallet]:
        wallets = {}
        all_dir = os.listdir(f"{self._root}/tracked_wallets/")
        for file_name in all_dir:
            if file_name[-5::] == ".json":
                address = file_name[0:-5]
                with open(f"{self._root}/tracked_wallets/{file_name}", mode="r") as f:
                    wallet = json.load(f)
                wallets[address] = wallet
        return wallets

    def track_new_wallet(self, address: str, name: str, group: str) -> None:
        file_path = f"{self._root}/tracked_wallets/{address}.json"
        data = {"name": name, "group": group, "last_updated_hash": None}
        with open(file_path, mode="w") as f:
            json.dump(data, f)

    def remove_wallet(self, address: str) -> None:
        file_path = f"{self._root}/tracked_wallets/{address}.json"
        os.remove(file_path)

    def get_server_params(self) -> ServerParams:
        file_path = f"{self._root}/server_params.json"
        with open(file_path, mode="r") as f:
            server_params = json.load(f)
        return server_params

    def update_server_params(self, **kwargs) -> None:
        file_path = f"{self._root}/server_params.json"
        with open(file_path, mode="r") as f:
            server_params = json.load(f)
        server_params.update(kwargs)
        with open(file_path, mode="w") as f:
            json.dump(server_params, f)
