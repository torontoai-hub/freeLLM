from __future__ import annotations

import pytest

from app.settings import get_settings
from app import main


@pytest.fixture(autouse=True)
def configure_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("VLLM_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv(
        "TOKENS_JSON",
        '[{"token":"test-token","label":"test","rpm":5,"rpd":10}]',
    )
    monkeypatch.setenv("RATE_LIMIT_STORE", "memory")
    get_settings.cache_clear()
    main.state = main.ProxyState()
    yield
    get_settings.cache_clear()
    main.state = main.ProxyState()
