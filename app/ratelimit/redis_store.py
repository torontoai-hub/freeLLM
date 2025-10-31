from __future__ import annotations

from redis import asyncio as aioredis

from app.ratelimit.base import RateLimitError, RateLimitResult, RateLimiter


class RedisRateLimiter(RateLimiter):
    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    async def _consume(self, key: str, limit: int, ttl: int) -> int:
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, ttl)
        if count > limit:
            raise RateLimitError("rate limit exceeded")
        return limit - count

    async def check_and_consume(self, token: str, rpm: int, rpd: int) -> RateLimitResult:
        minute_key = f"rl:{token}:minute"
        day_key = f"rl:{token}:day"

        remaining_minute = await self._consume(minute_key, rpm, 60)
        remaining_day = await self._consume(day_key, rpd, 86400)

        return RateLimitResult(
            limit_minute=rpm,
            remaining_minute=remaining_minute,
            limit_day=rpd,
            remaining_day=remaining_day,
        )
