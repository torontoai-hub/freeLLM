from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import main
from app.ratelimit.memory import MemoryRateLimiter

from .test_auth import DummyAdapter


@pytest.mark.anyio
async def test_rate_limit_exceeded():
    main.state.adapters["ollama"] = DummyAdapter()
    main.state.rate_limiter = MemoryRateLimiter()
    main.state.settings = main.get_settings()
    async with AsyncClient(transport=ASGITransport(app=main.app, lifespan=None), base_url="http://test") as client:
        for _ in range(5):
            response = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-token"},
                json={"model": "ollama:test", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.status_code == 200
        response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-token"},
            json={"model": "ollama:test", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 429
    payload = response.json()
    assert payload["error"]["type"] == "rate_limit_exceeded"
