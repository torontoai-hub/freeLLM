from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict

from fastapi import Request, Response

from app.utils.time import monotonic_ms, utcnow

LOGGER = logging.getLogger("app.request")


class RequestLogContext:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.start_ms = monotonic_ms()
        self.completed = False
        self.payload: Dict[str, Any] = {
            "ts": utcnow().isoformat(),
            "remote_ip": getattr(request.state, "remote_ip", None),
            "route": request.url.path,
            "token_label": getattr(request.state, "token_label", None),
            "model": None,
            "backend": None,
            "stream": False,
            "prompt_chars": None,
            "status_code": None,
            "latency_ms": None,
            "request_id": getattr(request.state, "request_id", None),
        }

    def update(self, **fields: Any) -> None:
        self.payload.update({k: v for k, v in fields.items() if v is not None})

    async def finish(self, status_code: int) -> None:
        if self.completed:
            return
        self.completed = True
        latency = monotonic_ms() - self.start_ms
        self.payload["latency_ms"] = latency
        self.payload["status_code"] = status_code
        LOGGER.info(json.dumps(self.payload, separators=(",", ":")))


async def logging_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    context = RequestLogContext(request)
    request.state.log_context = context
    try:
        response = await call_next(request)
    except Exception:
        await context.finish(status_code=500)
        raise

    async def on_close() -> None:
        await context.finish(response.status_code)

    response.call_on_close(on_close)
    return response


async def log_stream_response(
    iterator, *, context: RequestLogContext, status_code: int
):
    try:
        async for chunk in iterator:
            yield chunk
    finally:
        await context.finish(status_code)
