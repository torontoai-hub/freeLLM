from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import main
from app.ratelimit.memory import MemoryRateLimiter


class DummyAdapter:
    async def chat_completions(self, payload, stream: bool):
        if stream:
            async def iterator():
                yield b"data: {\"choices\":[{\"delta\":{\"content\":\"hi\"},\"index\":0,\"finish_reason\":null}]}\n\n"
                yield b"data: [DONE]\n\n"
            return iterator()
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": payload.get("response_model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hi"},
                    "finish_reason": "stop",
                }
            ],
        }

    async def completions(self, payload, stream: bool):
        return {
            "id": "cmpl-test",
            "object": "text_completion",
            "created": 0,
            "model": payload.get("response_model"),
            "choices": [
                {
                    "text": "hi",
                    "index": 0,
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
        }

    async def embeddings(self, payload):
        return {
            "data": [
                {"object": "embedding", "embedding": [0.1, 0.2], "index": 0}
            ],
            "model": payload.get("response_model"),
            "object": "list",
        }

    async def list_models(self):
        return []


@pytest.mark.anyio
async def test_missing_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=main.app, lifespan=None), base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json={"model": "ollama:test", "messages": []})
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


@pytest.mark.anyio
async def test_invalid_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=main.app, lifespan=None), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer wrong"},
            json={"model": "ollama:test", "messages": []},
        )
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


@pytest.mark.anyio
async def test_valid_token_passes_through(monkeypatch):
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
    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "hi"
