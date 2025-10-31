from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

from app import auth
from app.adapters.ollama import OllamaAdapter
from app.adapters.vllm import VLLMAdapter
from app.middleware.forwarded_ip import forwarded_ip_middleware
from app.middleware.logging import RequestLogContext, logging_middleware
from app.middleware.request_id import request_id_middleware
from app.ratelimit.base import RateLimitError, RateLimitResult, RateLimiter
from app.ratelimit.memory import MemoryRateLimiter
from app.schemas.openai_chat import ChatCompletionRequest
from app.schemas.openai_completions import CompletionRequest
from app.schemas.openai_embeddings import EmbeddingRequest
from app.settings import Settings, TokenConfig, get_settings
from app.utils.time import monotonic_ms

try:  # optional dependency
    from redis import asyncio as aioredis
    from app.ratelimit.redis_store import RedisRateLimiter
except Exception:  # pragma: no cover - optional
    aioredis = None
    RedisRateLimiter = None  # type: ignore[assignment]


logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="LLM Proxy", version="0.1.0")

app.middleware("http")(request_id_middleware)
app.middleware("http")(forwarded_ip_middleware)
app.middleware("http")(logging_middleware)


@app.middleware("http")
async def enforce_body_limit(request: Request, call_next):
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_body_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": {"message": "request body too large", "type": "invalid_request_error"}},
        )
    return await call_next(request)


class ProxyState:
    def __init__(self) -> None:
        self.settings: Settings | None = None
        self.adapters: Dict[str, Any] = {}
        self.rate_limiter: RateLimiter | None = None
        self.redis_client = None
        self.model_cache: Dict[str, Any] = {"expires": 0, "data": []}


state = ProxyState()


def get_adapter(name: str) -> Any:
    adapter = state.adapters.get(name)
    if adapter is None:
        raise HTTPException(status_code=500, detail={"error": {"message": "backend not available", "type": "backend_error"}})
    return adapter


def resolve_backend(model: str) -> Tuple[str, str]:
    settings = state.settings or get_settings()
    if model.startswith("ollama:"):
        return "ollama", model.split(":", 1)[1]
    if model.startswith("vllm:"):
        return "vllm", model.split(":", 1)[1]
    return settings.default_backend, model


async def startup_event() -> None:
    settings = get_settings()
    state.settings = settings
    if settings.ollama_enabled:
        state.adapters["ollama"] = OllamaAdapter(str(settings.ollama_base_url))
    if settings.vllm_enabled:
        state.adapters["vllm"] = VLLMAdapter(str(settings.vllm_base_url))

    if settings.rate_limit_store == "redis":
        if aioredis is None or RedisRateLimiter is None:
            raise RuntimeError("redis package not installed")
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL must be configured for redis rate limiter")
        state.redis_client = aioredis.from_url(settings.redis_url)
        state.rate_limiter = RedisRateLimiter(state.redis_client)  # type: ignore[arg-type]
    else:
        state.rate_limiter = MemoryRateLimiter()


async def shutdown_event() -> None:
    for adapter in state.adapters.values():
        close = getattr(adapter, "close", None)
        if close:
            await close()
    if state.redis_client is not None:
        await state.redis_client.close()


app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)


def ensure_rate_limiter() -> RateLimiter:
    if state.rate_limiter is None:
        state.rate_limiter = MemoryRateLimiter()
    return state.rate_limiter


async def apply_rate_limit(token: TokenConfig) -> RateLimitResult:
    limiter = ensure_rate_limiter()
    try:
        return await limiter.check_and_consume(token.token, token.rpm, token.rpd)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"message": exc.message, "type": "rate_limit_exceeded"}},
        ) from exc


def set_rate_headers(response: Response, result: RateLimitResult) -> None:
    response.headers["X-RateLimit-Limit-Minute"] = str(result.limit_minute)
    response.headers["X-RateLimit-Remaining-Minute"] = str(result.remaining_minute)
    response.headers["X-RateLimit-Limit-Day"] = str(result.limit_day)
    response.headers["X-RateLimit-Remaining-Day"] = str(result.remaining_day)


def estimate_prompt_chars_chat(payload: ChatCompletionRequest) -> int:
    return sum(len(msg.content) for msg in payload.messages)


def estimate_prompt_chars_completion(payload: CompletionRequest) -> int:
    if isinstance(payload.prompt, str):
        return len(payload.prompt)
    return sum(len(p) for p in payload.prompt)


def estimate_prompt_chars_embeddings(payload: EmbeddingRequest) -> int:
    if isinstance(payload.input, str):
        return len(payload.input)
    return sum(len(p) for p in payload.input)


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


async def proxy_models() -> list[dict[str, Any]]:
    settings = state.settings or get_settings()
    now = monotonic_ms()
    cache = state.model_cache
    if cache["expires"] > now:
        return cache["data"]
    models: list[dict[str, Any]] = []
    if settings.ollama_enabled:
        adapter = state.adapters.get("ollama")
        if adapter is not None:
            try:
                models.extend(await adapter.list_models())
            except Exception:
                logger.exception("failed to list ollama models")
    if settings.vllm_enabled:
        adapter = state.adapters.get("vllm")
        if adapter is not None:
            try:
                data = await adapter.list_models()
                for model in data:
                    model_id = model.get("id")
                    if not model_id:
                        continue
                    if model_id.startswith("vllm:"):
                        models.append(model)
                    else:
                        models.append({**model, "id": f"vllm:{model_id}"})
            except Exception:
                logger.exception("failed to list vllm models")
    cache["expires"] = now + settings.cache_models_ttl * 1000
    cache["data"] = models
    return models


@app.get("/v1/models")
async def list_models(token: TokenConfig = Depends(auth.require_token)) -> dict[str, Any]:
    models = await proxy_models()
    return {"data": models}


def build_backend_payload(body: dict[str, Any], response_model: str) -> dict[str, Any]:
    payload = dict(body)
    payload["response_model"] = response_model
    return payload


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    token: TokenConfig = Depends(auth.require_token),
):
    rate_info = await apply_rate_limit(token)
    backend_name, backend_model = resolve_backend(body.model)
    payload = body.model_dump(exclude_none=True)
    payload["model"] = backend_model
    payload = build_backend_payload(payload, body.model)

    adapter = get_adapter(backend_name)

    context: RequestLogContext | None = getattr(request.state, "log_context", None)
    if context:
        context.update(
            token_label=token.label,
            model=body.model,
            backend=backend_name,
            stream=bool(body.stream),
            prompt_chars=estimate_prompt_chars_chat(body),
        )

    try:
        if body.stream:
            iterator = await adapter.chat_completions(payload, stream=True)
            response = StreamingResponse(iterator, media_type="text/event-stream")
        else:
            data = await adapter.chat_completions(payload, stream=False)
            response = JSONResponse(content=data)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"message": str(exc), "type": "backend_error", "code": 502}},
        ) from exc

    response.headers["X-Proxy-Backend"] = backend_name
    set_rate_headers(response, rate_info)
    return response


@app.post("/v1/completions")
async def completions(
    request: Request,
    body: CompletionRequest,
    token: TokenConfig = Depends(auth.require_token),
):
    rate_info = await apply_rate_limit(token)
    backend_name, backend_model = resolve_backend(body.model)
    payload = body.model_dump(exclude_none=True)
    payload["model"] = backend_model
    payload = build_backend_payload(payload, body.model)
    adapter = get_adapter(backend_name)

    context: RequestLogContext | None = getattr(request.state, "log_context", None)
    if context:
        context.update(
            token_label=token.label,
            model=body.model,
            backend=backend_name,
            stream=bool(body.stream),
            prompt_chars=estimate_prompt_chars_completion(body),
        )

    try:
        if body.stream:
            iterator = await adapter.completions(payload, stream=True)
            response = StreamingResponse(iterator, media_type="text/event-stream")
        else:
            data = await adapter.completions(payload, stream=False)
            response = JSONResponse(content=data)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"message": str(exc), "type": "backend_error", "code": 502}},
        ) from exc

    response.headers["X-Proxy-Backend"] = backend_name
    set_rate_headers(response, rate_info)
    return response


@app.post("/v1/embeddings")
async def embeddings(
    request: Request,
    body: EmbeddingRequest,
    token: TokenConfig = Depends(auth.require_token),
):
    rate_info = await apply_rate_limit(token)
    backend_name, backend_model = resolve_backend(body.model)
    payload = body.model_dump(exclude_none=True)
    payload["model"] = backend_model
    payload = build_backend_payload(payload, body.model)
    adapter = get_adapter(backend_name)

    context: RequestLogContext | None = getattr(request.state, "log_context", None)
    if context:
        context.update(
            token_label=token.label,
            model=body.model,
            backend=backend_name,
            stream=False,
            prompt_chars=estimate_prompt_chars_embeddings(body),
        )

    try:
        data = await adapter.embeddings(payload)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"message": str(exc), "type": "backend_error", "code": 502}},
        ) from exc

    response = JSONResponse(content=data)
    response.headers["X-Proxy-Backend"] = backend_name
    set_rate_headers(response, rate_info)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {"error": {"message": exc.detail, "type": "invalid_request_error"}}
    return JSONResponse(status_code=exc.status_code, content=content)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
