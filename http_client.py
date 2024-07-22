import json
import httpx

from typing import Literal, Any


class Client:
    name: str
    url: str

    async def call(
        self, method: Literal["get", "post"], endpoint: str, **kwargs: Any
    ) -> dict | list:
        client = httpx.AsyncClient()
        response = await getattr(client, method)(f"{self.url}{endpoint}", **kwargs)
        status_code = response.status_code
        if response.status_code != 200:
            raise Exception(
                f"{self.url} failed with status code {status_code}: {response.text}"
            )
        else:
            try:
                return json.loads(response.text)
            except:
                raise Exception(f"{self.url} failed to parse response")
