from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app import main
from app.ratelimit.memory import MemoryRateLimiter

from .test_auth import DummyAdapter


@pytest.mark.anyio
async def test_chat_completion_schema_matches():
    main.state.adapters["ollama"] = DummyAdapter()
    main.state.rate_limiter = MemoryRateLimiter()
    main.state.settings = main.get_settings()
    async with AsyncClient(transport=ASGITransport(app=main.app, lifespan=None), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-token"},
            json={
                "model": "ollama:test",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        body = response.json()
        assert body["id"].startswith("chatcmpl")
        assert body["object"] == "chat.completion"
        assert body["choices"][0]["message"]["role"] == "assistant"

        stream_response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-token"},
            json={
                "model": "ollama:test",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            stream=True,
        )
        chunks = []
        async for line in stream_response.aiter_lines():
            if not line:
                continue
            if line == "data: [DONE]":
                chunks.append(line)
                break
            payload = json.loads(line.removeprefix("data: "))
            assert payload["object"] == "chat.completion.chunk"
            chunks.append(line)
        assert "data: [DONE]" in chunks
