from __future__ import annotations

import time
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def monotonic_ms() -> int:
    """Return monotonic time in milliseconds."""
    return int(time.monotonic() * 1000)
