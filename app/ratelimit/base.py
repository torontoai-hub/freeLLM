from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RateLimitResult:
    limit_minute: int
    remaining_minute: int
    limit_day: int
    remaining_day: int


class RateLimitError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RateLimiter(Protocol):
    async def check_and_consume(self, token: str, rpm: int, rpd: int) -> RateLimitResult:
        ...
