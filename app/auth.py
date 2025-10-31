from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, Request, status

from app.settings import TokenConfig, get_settings


class TokenRegistry:
    def __init__(self, tokens: list[TokenConfig]):
        self._tokens: Dict[str, TokenConfig] = {t.token: t for t in tokens}

    def get(self, token: str) -> TokenConfig | None:
        return self._tokens.get(token)


_registry: TokenRegistry | None = None


def get_registry() -> TokenRegistry:
    global _registry
    if _registry is None:
        settings = get_settings()
        _registry = TokenRegistry(settings.tokens_json)
    return _registry


def get_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip()


async def require_token(request: Request) -> TokenConfig:
    token_value = get_bearer_token(request)
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "missing bearer token", "type": "authentication_error"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_info = get_registry().get(token_value)
    if token_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "invalid bearer token", "type": "authentication_error"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.token = token_info
    request.state.token_label = token_info.label
    return token_info
