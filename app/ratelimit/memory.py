from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.ratelimit.base import RateLimitError, RateLimitResult, RateLimiter


@dataclass
class TokenWindow:
    minute_bucket: int = 0
    minute_count: int = 0
    day_bucket: int = 0
    day_count: int = 0


class MemoryRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._state: dict[str, TokenWindow] = {}

    async def check_and_consume(self, token: str, rpm: int, rpd: int) -> RateLimitResult:
        now = time.time()
        minute_bucket = int(now // 60)
        day_bucket = int(now // 86400)

        async with self._lock:
            window = self._state.setdefault(token, TokenWindow())

            if window.minute_bucket != minute_bucket:
                window.minute_bucket = minute_bucket
                window.minute_count = 0

            if window.day_bucket != day_bucket:
                window.day_bucket = day_bucket
                window.day_count = 0

            if window.minute_count >= rpm:
                raise RateLimitError("minute limit reached")
            if window.day_count >= rpd:
                raise RateLimitError("daily limit reached")

            window.minute_count += 1
            window.day_count += 1

            remaining_minute = max(rpm - window.minute_count, 0)
            remaining_day = max(rpd - window.day_count, 0)

            return RateLimitResult(
                limit_minute=rpm,
                remaining_minute=remaining_minute,
                limit_day=rpd,
                remaining_day=remaining_day,
            )
