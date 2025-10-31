from __future__ import annotations

from typing import Any, AsyncIterator, Protocol


class BackendAdapter(Protocol):
    async def chat_completions(self, payload: dict[str, Any], stream: bool) -> Any:
        ...

    async def completions(self, payload: dict[str, Any], stream: bool) -> Any:
        ...

    async def embeddings(self, payload: dict[str, Any]) -> Any:
        ...

    async def list_models(self) -> list[dict[str, Any]]:
        ...
