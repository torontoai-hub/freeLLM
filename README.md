# LLM Proxy

A lightweight FastAPI control-plane that exposes OpenAI-compatible endpoints and proxies
requests to Ollama and vLLM backends. An accompanying Nginx configuration performs the heavy
lifting for HTTP proxying, streaming, and logging so the Python code can focus on authentication,
rate limiting, and Ollama protocol adaptation.

## Features

- `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings` compatible with OpenAI SDKs
- Static routing via `ollama:` or `vllm:` prefixes (with configurable default)
- Bearer token authentication backed by environment-provided registry
- Per-token RPM/RPD rate limiting (in-memory or Redis)
- Designed to sit behind Nginx which provides request logging, buffering, and TLS termination
- Streaming support when `stream=true`

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
   uvicorn app.main:app --host ${HOST:-127.0.0.1} --port ${PORT:-8080}
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

## Fronting with Nginx

The repository ships with `nginx/nginx.conf`, which demonstrates how to offload the bulk of the
proxy responsibilities to Nginx:

1. `auth_request` sends an internal call to `FastAPI /internal/authz`, which validates the bearer
   token, enforces rate limits, and responds with headers that declare the chosen backend.
2. A `map` uses the returned `X-Proxy-Backend` header to route OpenAI-compatible calls either to
   the local FastAPI service (for Ollama translation) or directly to a remote vLLM server.
3. Rate-limit headers emitted by the auth request are added to the final client response and the
   `X-RateLimit-Checked` header avoids re-running the limiter inside the application.

Update the `vllm_backend` upstream in `nginx/nginx.conf` to point at your vLLM host, then start the
two services (FastAPI on localhost and Nginx bound to the public interface). Clients only interact
with Nginx, while the Python code remains focused on the tasks that cannot be handled by the proxy.

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

Request logging is delegated to Nginx. Application logs only cover startup events and backend
errors, keeping the Python service minimal.
