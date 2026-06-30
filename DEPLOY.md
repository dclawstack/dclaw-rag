# Deploying DCLAW RAG

## Services

| Service   | What it is                          | Scales by |
|-----------|-------------------------------------|-----------|
| backend   | FastAPI API (`uvicorn`)             | replicas (each loads the models, ~2.5 GB RAM) |
| worker    | Celery worker for async ingestion   | replicas / `--concurrency` |
| qdrant    | Vector store (named dense + sparse) | managed / stateful set |
| redis     | API keys, collections, document registry, Celery broker, rate-limit counters | managed |
| frontend  | Next.js UI                          | replicas |

The backend and worker share one image (`Dockerfile`); the worker just overrides the
command. Both run as a non-root user.

## Local / demo stack

```bash
docker compose up --build
# API   → http://localhost:8090   (docs at /docs)
# UI    → http://localhost:3003
```

Compose runs with `APP_ENV=dev`, so the production config checks below are not enforced.

## Production

### 1. Configuration (fail-fast)

When `APP_ENV=production`, the app **validates its config on startup and refuses to boot**
if any of these are wrong (see `validate_runtime_config`):

- `ADMIN_API_KEY` must be set (it gates tenant-key minting) and must not be a dev placeholder.
- `BOOTSTRAP_API_KEY`, if set, must not be a dev placeholder.
- `JWT_SECRET` must be a strong, unique value (≥32 chars) — it signs end-user login tokens.
- `CORS_ALLOW_ORIGINS` must not be `*`.
- The selected `LLM_PROVIDER` must have its key set (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` /
  `OPENROUTER_API_KEY`; `ollama` needs none).

Required/important environment (see `.env.example` for the full list):

```
APP_ENV=production
ADMIN_API_KEY=<strong secret>            # mint tenant keys via POST /api/v1/rag/keys
JWT_SECRET=<strong secret, >=32 chars>   # signs end-user login tokens
CORS_ALLOW_ORIGINS=["https://your-ui"]   # JSON list of allowed browser origins
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
LLM_PROVIDER=openrouter                   # or openai | anthropic | ollama
OPENROUTER_API_KEY=<...>                  # the key for the chosen provider
RATE_LIMIT_PER_MINUTE=60                  # per tenant; 0 disables
```

### 2. Run

```bash
# web (one model-loading process per replica; scale horizontally)
uvicorn app.api.main:app --host 0.0.0.0 --port 8090

# ingestion worker (separate process/replica)
celery -A app.worker.celery_app worker --queues ingestion --concurrency 2
```

Provision managed **Qdrant** and **Redis** (or run the compose ones).

### 3. Probes & metrics

- `GET /health` — liveness (process up).
- `GET /health/ready` — readiness; returns **503** until Redis **and** Qdrant are reachable.
  Use this for the container/k8s readiness probe (the Docker `HEALTHCHECK` and compose use it).
- `GET /metrics` — Prometheus exposition (HTTP + RAG counters/histograms).

### 4. Notes

- **Cold start:** embedding + reranker models (~2.5 GB) download/load lazily on first use.
  Expect a slow first request per replica; pre-warm by hitting `/api/v1/rag/query` after deploy.
- **Auth:** every `/api/v1/rag/*` route requires `Authorization: Bearer <token>`, which is
  either an **end-user JWT** (self-serve `POST /auth/register` / `/auth/login`; each account
  is its own tenant) or a **machine API key** minted with the admin key. The browser uses the
  JWT; `NEXT_PUBLIC_API_KEY` is a dev bypass — leave it unset in production so the UI requires
  login.
- A Helm chart skeleton lives in `helm/`.
