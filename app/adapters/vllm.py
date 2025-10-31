from __future__ import annotations

from typing import Any, AsyncIterator

import httpx


class VLLMAdapter:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any], stream: bool) -> Any:
        if stream:
            response = await self._client.stream("POST", path, json=payload)
            response.raise_for_status()

            async def iterator() -> AsyncIterator[bytes]:
                async with response:
                    async for chunk in response.aiter_raw():
                        yield chunk

            return iterator()
        response = await self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    async def chat_completions(self, payload: dict[str, Any], stream: bool) -> Any:
        return await self._post("/v1/chat/completions", payload, stream)

    async def completions(self, payload: dict[str, Any], stream: bool) -> Any:
        return await self._post("/v1/completions", payload, stream)

    async def embeddings(self, payload: dict[str, Any]) -> Any:
        response = await self._client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        return response.json()

    async def list_models(self) -> list[dict[str, Any]]:
        response = await self._client.get("/v1/models")
        response.raise_for_status()
        body = response.json()
        return body.get("data", [])
