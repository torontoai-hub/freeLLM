from __future__ import annotations

import json
from typing import AsyncIterable, AsyncIterator, Awaitable, Callable, Optional


async def iterate_with_callback(
    iterator: AsyncIterable[str],
    *,
    on_complete: Optional[Callable[[], Awaitable[None]]] = None,
    on_error: Optional[Callable[[BaseException], Awaitable[None]]] = None,
) -> AsyncIterator[str]:
    try:
        async for chunk in iterator:
            yield chunk
    except BaseException as exc:  # pragma: no cover - defensive
        if on_error is not None:
            await on_error(exc)
        raise
    else:
        if on_complete is not None:
            await on_complete()


def sse_format(data: dict) -> str:
    return f"data: {json.dumps(data, separators=(",", ":"))}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"
