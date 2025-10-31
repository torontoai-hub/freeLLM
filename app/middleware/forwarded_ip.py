from __future__ import annotations

from typing import Callable

from fastapi import Request, Response


def extract_remote_ip(request: Request) -> str | None:
    header = request.headers.get("x-forwarded-for")
    if header:
        return header.split(",")[0].strip()
    client = request.client
    if client is not None:
        return client.host
    return None


async def forwarded_ip_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    request.state.remote_ip = extract_remote_ip(request)
    return await call_next(request)
