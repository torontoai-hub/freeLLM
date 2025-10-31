from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request, Response


async def request_id_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers.setdefault("X-Request-ID", request_id)
    return response
