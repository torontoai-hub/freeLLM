from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

from app.schemas.openai_common import ChatMessage
from app.utils.sse import sse_done, sse_format


def _timestamp(created_at: str | None) -> int:
    if not created_at:
        return int(time.time())
    try:
        return int(datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return int(time.time())


def _extract_options(payload: dict[str, Any]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if (temperature := payload.get("temperature")) is not None:
        options["temperature"] = temperature
    if (top_p := payload.get("top_p")) is not None:
        options["top_p"] = top_p
    if (seed := payload.get("seed")) is not None:
        options["seed"] = seed
    if (max_tokens := payload.get("max_tokens")) is not None:
        options["num_predict"] = max_tokens
    return options


class OllamaAdapter:
    def __init__(self, base_url: str, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_completions(self, payload: dict[str, Any], stream: bool) -> Any:
        request_body = {
            "model": payload["model"],
            "messages": [message.model_dump() if isinstance(message, ChatMessage) else message for message in payload["messages"]],
            "stream": stream,
            "options": _extract_options(payload),
        }
        if not request_body["options"]:
            request_body.pop("options")
        if payload.get("stop") is not None:
            request_body["stop"] = payload["stop"]

        if stream:
            response = await self._client.stream("POST", "/api/chat", json=request_body)
            response.raise_for_status()
            stream_id = f"chatcmpl-{uuid.uuid4().hex}"
            created = int(time.time())

            response_model = payload.get("response_model", payload["model"])

            async def iterator() -> AsyncIterator[bytes]:
                role_sent = False
                finish_reason = "stop"
                async with response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("done"):
                            finish_reason = data.get("done_reason", "stop") or "stop"
                            chunk = {
                                "id": stream_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": response_model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": finish_reason,
                                    }
                                ],
                            }
                            yield sse_format(chunk).encode("utf-8")
                            yield sse_done().encode("utf-8")
                            return
                        message = data.get("message") or {}
                        content = message.get("content") or ""
                        delta: dict[str, Any] = {}
                        if not role_sent:
                            delta["role"] = "assistant"
                            role_sent = True
                        if content:
                            delta["content"] = content
                        if delta:
                            chunk = {
                                "id": stream_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": response_model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": delta,
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield sse_format(chunk).encode("utf-8")
                chunk = {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": response_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": finish_reason,
                        }
                    ],
                }
                yield sse_format(chunk).encode("utf-8")
                yield sse_done().encode("utf-8")

            return iterator()

        response = await self._client.post("/api/chat", json=request_body)
        response.raise_for_status()
        data = response.json()
        created = _timestamp(data.get("created_at"))
        message = data.get("message") or {}
        content = message.get("content", "")
        usage = None
        if "eval_count" in data or "prompt_eval_count" in data:
            completion_tokens = data.get("eval_count")
            prompt_tokens = data.get("prompt_eval_count")
            total = None
            if completion_tokens is not None and prompt_tokens is not None:
                total = completion_tokens + prompt_tokens
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
            }
        response_model = payload.get("response_model", payload["model"])
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created,
            "model": response_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": data.get("done_reason", "stop") or "stop",
                }
            ],
            "usage": usage,
        }

    async def completions(self, payload: dict[str, Any], stream: bool) -> Any:
        request_body: dict[str, Any] = {
            "model": payload["model"],
            "prompt": payload["prompt"],
            "stream": stream,
            "options": _extract_options(payload),
        }
        if not request_body["options"]:
            request_body.pop("options")
        if payload.get("stop") is not None:
            request_body["stop"] = payload["stop"]

        if stream:
            response = await self._client.stream("POST", "/api/generate", json=request_body)
            response.raise_for_status()
            stream_id = f"cmpl-{uuid.uuid4().hex}"
            created = int(time.time())
            response_model = payload.get("response_model", payload["model"])

            async def iterator() -> AsyncIterator[bytes]:
                async with response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("done"):
                            chunk = {
                                "id": stream_id,
                                "object": "text_completion",
                                "created": created,
                                "model": response_model,
                                "choices": [
                                    {
                                        "text": "",
                                        "index": 0,
                                        "logprobs": None,
                                        "finish_reason": data.get("done_reason", "stop") or "stop",
                                    }
                                ],
                            }
                            yield sse_format(chunk).encode("utf-8")
                            yield sse_done().encode("utf-8")
                            return
                        text = data.get("response", "")
                        chunk = {
                            "id": stream_id,
                            "object": "text_completion",
                            "created": created,
                            "model": response_model,
                            "choices": [
                                {
                                    "text": text,
                                    "index": 0,
                                    "logprobs": None,
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield sse_format(chunk).encode("utf-8")
                chunk = {
                    "id": stream_id,
                    "object": "text_completion",
                    "created": created,
                    "model": response_model,
                    "choices": [
                        {
                            "text": "",
                            "index": 0,
                            "logprobs": None,
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield sse_format(chunk).encode("utf-8")
                yield sse_done().encode("utf-8")

            return iterator()

        response = await self._client.post("/api/generate", json=request_body)
        response.raise_for_status()
        data = response.json()
        created = _timestamp(data.get("created_at"))
        text = data.get("response", "")
        usage = None
        if "eval_count" in data or "prompt_eval_count" in data:
            completion_tokens = data.get("eval_count")
            prompt_tokens = data.get("prompt_eval_count")
            total = None
            if completion_tokens is not None and prompt_tokens is not None:
                total = completion_tokens + prompt_tokens
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
            }
        response_model = payload.get("response_model", payload["model"])
        return {
            "id": f"cmpl-{uuid.uuid4().hex}",
            "object": "text_completion",
            "created": created,
            "model": response_model,
            "choices": [
                {
                    "text": text,
                    "index": 0,
                    "logprobs": None,
                    "finish_reason": data.get("done_reason", "stop") or "stop",
                }
            ],
            "usage": usage,
        }

    async def embeddings(self, payload: dict[str, Any]) -> Any:
        request_body = {
            "model": payload["model"],
            "prompt": payload.get("input"),
        }
        response = await self._client.post("/api/embeddings", json=request_body)
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding", [])
        response_model = payload.get("response_model", payload["model"])
        return {
            "data": [
                {
                    "object": "embedding",
                    "embedding": embedding,
                    "index": 0,
                }
            ],
            "model": response_model,
            "object": "list",
        }

    async def list_models(self) -> list[dict[str, Any]]:
        response = await self._client.get("/api/tags")
        response.raise_for_status()
        body = response.json()
        models = []
        for item in body.get("models", []):
            model_id = item.get("name")
            if not model_id:
                continue
            models.append(
                {
                    "id": f"ollama:{model_id}",
                    "object": "model",
                    "owned_by": "ollama",
                }
            )
        return models
