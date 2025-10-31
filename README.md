# LLM Proxy

A lightweight FastAPI service that exposes OpenAI-compatible endpoints and proxies requests to
Ollama and vLLM backends.

## Features

- `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings` compatible with OpenAI SDKs
- Static routing via `ollama:` or `vllm:` prefixes (with configurable default)
- Bearer token authentication backed by environment-provided registry
- Per-token RPM/RPD rate limiting (in-memory or Redis)
- Structured JSON logging and request metadata capture
- Streaming support via Server-Sent Events

## Getting Started

1. Clone the repository and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy the sample environment file and update values as needed:

   ```bash
   cp .env.example .env
   ```

3. Run the service with Uvicorn:

   ```bash
   uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}
   ```

4. Test with the OpenAI Python client:

   ```python
   from openai import OpenAI

   client = OpenAI(api_key="demo-key-123", base_url="http://localhost:8080/v1")
   response = client.chat.completions.create(
       model="ollama:llama3",
       messages=[{"role": "user", "content": "Hello!"}],
   )
   print(response)
   ```

## Docker

A minimal container image can be built with the included Dockerfile:

```bash
docker build -t llm-proxy .
docker run -p 8080:8080 --env-file .env llm-proxy
```

## Testing

Run the pytest suite:

```bash
pytest
```

## Environment Variables

Key settings are documented in `.env.example`.

- `DEFAULT_BACKEND`: `ollama` or `vllm`
- `OLLAMA_BASE_URL` / `VLLM_BASE_URL`: upstream service URLs
- `TOKENS_JSON`: JSON array of token definitions (`token`, `label`, `rpm`, `rpd`)
- `RATE_LIMIT_STORE`: `memory` or `redis`
- `REDIS_URL`: Redis connection string (required when `RATE_LIMIT_STORE=redis`)
- `MAX_BODY_BYTES`: maximum request size in bytes

## Logging

Logs are emitted as JSON lines to stdout with metadata including request id, remote IP,
backend, latency, and status code. Integrate with your log aggregation tooling for
observability.
