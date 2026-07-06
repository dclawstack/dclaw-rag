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

### 4. Durability & backups

Redis is the source of truth for **users, API keys, collections, and the document
registry** — treat it as a database, not a cache.

- **Persistence:** the compose Redis runs with **AOF** (`--appendonly yes`) on a named
  volume, so data survives restarts. In Kubernetes, point `config.redisUrl` at a **managed
  Redis with persistence + replication** (or a StatefulSet with a PVC + AOF). Don't run
  production on an ephemeral Redis.
- **Backups:** `scripts/backup.py export backup.json` writes a portable logical snapshot of
  the durable keys (restore with `... restore backup.json`) — run it on a schedule and store
  the output off-box, in addition to Redis's own persistence.
- Qdrant holds the vectors; use its snapshot API / a persistent volume for the collection.

### 5. Notes

- **Cold start:** embedding + reranker models (~2.5 GB) download/load lazily on first use.
  Expect a slow first request per replica; pre-warm by hitting `/api/v1/rag/query` after deploy.
- **Auth:** every `/api/v1/rag/*` route requires `Authorization: Bearer <token>`, which is
  either an **end-user JWT** (self-serve `POST /auth/register` / `/auth/login`; each account
  is its own tenant) or a **machine API key** minted with the admin key. The browser uses the
  JWT; `NEXT_PUBLIC_API_KEY` is a dev bypass — leave it unset in production so the UI requires
  login.
## Kubernetes (Helm)

The chart in `helm/` deploys the backend, worker, and frontend (point it at managed
Qdrant + Redis via `config.qdrantUrl` / `config.redisUrl`). Probes are wired to the real
endpoints — liveness `/health`, readiness `/health/ready` — and `metrics.serviceMonitor.enabled=true`
scrapes `/metrics` via the Prometheus Operator.

```bash
helm upgrade --install dclaw helm/ \
  --set secrets.adminApiKey=<...> \
  --set secrets.jwtSecret=<strong, >=32 chars> \
  --set secrets.openrouterApiKey=<...> \
  --set config.corsAllowOrigins='["https://your-ui"]'
```

Images are published to GHCR on a version tag (`v*`) by `.github/workflows/release.yml`
(`ghcr.io/dclawstack/dclaw-rag-backend` and `-frontend`); `helm lint` runs on every chart
change. The frontend image bakes `NEXT_PUBLIC_API_URL` at build time, so rebuild it per
environment (or pass `--build-arg`). No automated cluster rollout ships in this repo — add a
deploy job with your kubeconfig when you have a target.
