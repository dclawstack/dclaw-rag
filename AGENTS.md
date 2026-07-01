# DClaw RAG — Agent Development Guide

> **Read this file first before making any code changes.**
> Source of truth for this app's architecture, conventions, and workflow.
> Broad rules live here; concrete details live next to the code.

## App Identity

**DClaw RAG** — a retrieval-augmented generation service: ingest documents, then ask
questions and get cited, LLM-synthesized answers.

- **Backend:** FastAPI, port `8090`
- **Frontend:** Next.js (App Router), port `3003`
- **Base API path:** `/api/v1/rag` (health probe is at `/health`)
- **Vector store:** Qdrant · **Cache + collection metadata:** Redis

> ⚠️ This app does **NOT** use PostgreSQL, SQLAlchemy, Alembic, or a repository layer.
> State lives in Qdrant (vectors) and Redis (collection records). Do not reintroduce a
> relational-DB/ORM layer unless the architecture genuinely changes.

## Architecture

### Backend (`app/`, at the repo root — not `backend/`)
- **FastAPI** + **Pydantic v2** schemas (`app/models/schemas.py`).
- **Dependency injection** via `Depends(...)` (`app/api/dependencies.py`); heavy clients
  (Qdrant, embedders, LLM, collection store) are lazily created and cached on `app.state`.
- **Retrieval is hybrid:** dense (bge-large via sentence-transformers) **+** sparse/BM25
  (fastembed `Qdrant/bm25`), fused with **Reciprocal Rank Fusion**, then re-ranked with a
  cross-encoder. See `app/retrieval/`.
- **Qdrant** uses **named vectors**: `dense` (1024-d cosine) + `sparse`. See
  `app/db/qdrant_store.py`.
- **Collections** are lightweight metadata records persisted in **Redis**
  (`app/db/collection_store.py`); documents are associated via `metadata.collection_id`.
- **Query caching** (`app/db/query_cache.py`): `/query` responses are cached per tenant in
  Redis (TTL `query_cache_ttl_seconds`); a hit skips retrieval + the LLM. Keys embed a
  per-tenant version that the worker bumps when a document finishes ingesting, so new data
  invalidates cached answers instantly. `rag_query_cache_total{result}` on `/metrics`.
- **Documents** are tracked in a **Redis registry** (`app/db/document_store.py`) — the
  source of truth for document listing/counts and ingestion **status** (pending →
  processing → ready/failed). Qdrant holds the chunks; tenant/collection/doc payload
  indexes keep counts and filtered search off a full scan.
- **Ingestion is async:** the route extracts text, registers a `pending` document, and
  enqueues a **Celery** task (`app/ingestion/tasks.py`, `app/worker.py`) that does the heavy
  chunk → embed → upsert off the request path and updates status. Idempotent by content
  checksum. Run a worker: `celery -A app.worker.celery_app worker --queues ingestion`.
  Supported formats live in `app/ingestion/extractors/` + the `loaders` registry (PDF,
  DOCX, HTML, CSV/TSV, Markdown, plaintext).
- **Generation** (`app/generation/`): `LLMGateway` (OpenAI / Anthropic) + Jinja prompt.
- **Auth** (`app/core/security.py`, `app/db/user_store.py`, `app/db/refresh_token_store.py`,
  `app/api/routes/auth.py`): two credential types resolve to a tenant via `get_principal` —
  **end-user JWTs** (email+password signup/login, argon2 hashes in Redis; each signup gets its
  own tenant) and **machine API keys** (admin-minted). Access tokens are short-lived and
  stateless; **refresh tokens are stored in Redis and revocable** — `/auth/refresh` rotates,
  `/auth/logout` revokes the session, `/auth/logout-all` revokes every session. The frontend
  stores both tokens and silently refreshes on a 401; `NEXT_PUBLIC_API_KEY` is a dev bypass.
- **Security/abuse** (`app/api/middleware.py`, `app/db/rate_limiter.py`): per-tenant rate limit
  on query/agent/ingest (429 + `Retry-After`); request-body and upload size caps (413);
  security headers on every response; request schemas carry length/range bounds. Limits live
  in `settings`.
- **Observability** (`app/api/middleware.py`, `app/core/metrics.py`): every request gets an
  `X-Request-ID` (echoed if supplied) bound into a structured access log (method, path,
  status, duration). Prometheus at **`GET /metrics`** (HTTP counter/histogram + RAG query/
  ingest counters); the query route logs per-stage (retrieval/generation) latency.
  **`GET /health/ready`** checks Redis + Qdrant (503 if down); `GET /health` is liveness.
- **Usage/cost metering** (`app/core/metering.py`, `app/db/usage_store.py`): the LLM gateways
  report token usage against the caller's tenant (carried on a contextvar set in
  `get_principal`). Aggregate token/cost counters go to Prometheus (labelled by model — not
  tenant, to bound cardinality); per-tenant totals accrue in Redis and are read via
  **`GET /usage`**. Pricing is configurable (`llm_price_per_1k_*_usd`). Metering is
  best-effort — it never fails a request.
- **Logging:** `structlog` (`app/core/logging.py`) — no `print()`, and never log key values.

### Frontend (`frontend/`)
- **Next.js 14+ App Router**, **Tailwind**, pre-built UI components in
  `src/components/ui/` (use them; the project uses `@base-ui/react` primitives).
- **API client** in `src/lib/api.ts` — a typed fetch wrapper. It is the contract with the
  backend; keep paths/shapes in sync with the FastAPI routes.
- **`NEXT_PUBLIC_API_URL`** is baked at build time; the frontend Dockerfile MUST declare
  `ARG NEXT_PUBLIC_API_URL` before `npm run build`.
- A floating **Copilot** (`src/components/copilot.tsx`) is mounted in the root layout and
  appears on every route.

## Directory Structure

```
dclaw-rag/
├── app/                          # FastAPI backend (import root: `app.`)
│   ├── api/
│   │   ├── main.py               # app + router mounts
│   │   ├── dependencies.py       # Depends(...) providers
│   │   └── routes/               # health, query, ingest, collections
│   ├── core/                     # config (pydantic-settings), logging, exceptions
│   ├── db/                       # qdrant_store, collection_store (Redis), cache
│   ├── generation/               # LLM gateway, prompts, output models
│   ├── ingestion/                # pipeline, chunkers, extractors, loaders
│   ├── models/schemas.py         # Pydantic v2 request/response models
│   └── retrieval/                # embedder (dense+sparse), reranker, search (RRF)
├── frontend/                     # Next.js app (see its own conventions above)
├── tests/                        # pytest (unit/ + integration/)
├── eval/                         # golden_set.json for the RAG eval harness
├── scripts/                      # ingest_folder, evaluate (RAG eval), evaluate_retrieval
├── helm/                         # K8s manifests
├── infra/docker-compose.yml      # full dev stack (api + qdrant + redis)
├── docker-compose.yml            # app + qdrant + redis
├── Dockerfile                    # backend image
├── pyproject.toml                # deps + ruff/mypy/pytest config
└── .env.example                  # all settings (mirror of app/core/config.py)
```

## Conventions

### Python
- `ruff` (config in `pyproject.toml`) and type hints on public APIs.
- Pydantic v2 for all schemas; SQLAlchemy is **not** used.
- `pytest` + `pytest-asyncio` (`asyncio_mode = auto`).
- Functions < 50 lines; `structlog`, never `print()`.

### TypeScript / Next.js
- Strict TypeScript; Tailwind for styling; `cn()` for conditional classes.
- Do NOT install the shadcn CLI — use the pre-built components in `src/components/ui/`.

### API contract
- All app endpoints live under `/api/v1/rag` (health is the lone exception at `/health`).
- When you change a route's path or response shape, update `frontend/src/lib/api.ts` (and
  any page using it) in the same change. A mismatch here silently breaks the UI.

## How to Add a Feature
1. **Read this file.** Check `REVISED-PRD.md` / `PLAN-v1.2.md` for product context.
2. **Backend:** add/update a Pydantic schema in `app/models/schemas.py`, the logic in the
   relevant `app/` package, and a router in `app/api/routes/` (mounted in `app/api/main.py`).
   Add tests in `tests/`.
3. **Frontend:** add the typed call in `src/lib/api.ts`, then the page/component.
4. **Verify:** `ruff check`, `mypy app/`, `pytest`, `cd frontend && npm run build && npm run lint`,
   and `docker compose config`.

Deployment (images, env, probes, prod config validation) is documented in `DEPLOY.md`.
`APP_ENV=production` makes the app validate its config on startup and refuse to boot if
secrets/CORS/LLM-provider keys are missing (`validate_runtime_config`).

## Testing & quality gates
- `pytest` from the repo root. Tests use `httpx.AsyncClient` + `ASGITransport` and override
  the `Depends(...)` providers (`tests/conftest.py`) — **no external services required**.
- Every new router endpoint should have an integration test; new pure logic gets a unit test.
- CI (`.github/workflows/ci.yml`) runs the blocking gates on every PR: **ruff**, **mypy**,
  **pip-audit**, **pytest** (backend) and **eslint** + **next build** (frontend).
  `claude-code-review.yml` runs an automated review on PRs.
- **RAG quality eval** (`.github/workflows/eval.yml`, `scripts/evaluate.py`) runs nightly, on
  demand, and on retrieval-touching PRs: it ingests `eval/golden_set.json` into a throwaway
  Qdrant collection and gates on hit-rate / MRR / abstention accuracy (no LLM needed). It also
  does **LLM-graded answer quality** — but only when a provider key is configured (the secret
  is passed in CI); without one it's skipped, not failed.

## Running Locally
- **Python deps:** install CPU-only torch first, then the package — the app runs on CPU,
  and the default `torch` (a transitive dep) otherwise pulls ~5GB of unused CUDA wheels:
  `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install -e ".[dev]"`.
  (The Dockerfile and CI do this automatically.)
- **Backend deps:** Qdrant (`:6333`) and Redis (`:6379`) — start them via
  `docker compose up qdrant redis` (or the full stack with `docker compose up`).
- **Config:** copy `.env.example` → `.env`; set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for
  generation. All settings map 1:1 to `app/core/config.py`.
- **First run** creates the Qdrant collection with named `dense`+`sparse` vectors. If you
  have an older single-vector collection, drop it and re-ingest.

## Anti-Patterns — Avoid

| Anti-pattern | Why | Instead |
|--------------|-----|---------|
| Reintroducing Postgres / SQLAlchemy / Alembic | This app is Qdrant + Redis only | Use Qdrant for vectors, Redis for metadata |
| Changing a backend route without updating `src/lib/api.ts` | Silently breaks the UI | Update both sides together |
| Mounting an endpoint outside `/api/v1/rag` | Frontend assumes that prefix | Keep the prefix (health excepted) |
| `curl` in a `python:*-slim` healthcheck | No `curl` in the image | `python -c "import urllib.request; urllib.request.urlopen(...)"` |
| Frontend Dockerfile without `ARG NEXT_PUBLIC_API_URL` | Wrong API URL baked in | Declare the ARG before `npm run build` |
| Single unnamed Qdrant vector | Hybrid search needs `dense`+`sparse` | Use named vectors (see `qdrant_store.py`) |
| `print()` for diagnostics | Unstructured logs | `structlog` |

## Notes / Known Gaps
- The `LLMGateway` supports OpenAI/Anthropic, with an automatic local **Ollama** fallback
  when the cloud provider errors (`FallbackGateway`; toggle via `LLM_FALLBACK_TO_OLLAMA`).
- A `celery`/`app.tasks` worker is referenced in `infra/docker-compose.yml` but the task
  module does not exist yet.
- Agentic (multi-step) RAG is not implemented (PRD P0.4).
