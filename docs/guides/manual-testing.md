# Manual Testing

How to bring the app up locally and exercise every feature by hand.

## Prerequisites

- **Docker** — for Qdrant (vector store) and Redis (collection metadata).
- **An LLM key** — ingestion and retrieval work without one, but `query` and `agent`
  answer generation need it. Set `OPENAI_API_KEY` (default), or `ANTHROPIC_API_KEY` with
  `LLM_PROVIDER=anthropic`, or run a local Ollama.
- The **first** ingest/query downloads embedding/rerank models (~1.3 GB) — that call is slow;
  later calls are fast.

```bash
cp .env.example .env      # then set OPENAI_API_KEY=sk-...
```

## Option A — Full stack via Docker

```bash
docker compose up --build      # qdrant, redis, backend (:8090), frontend (:3003)
```

The dev compose does not forward your LLM key automatically — add `OPENAI_API_KEY` under the
`backend` service's `environment:` (or an `env_file: .env`). Then open http://localhost:3003.

## Option B — Local dev (faster iteration)

```bash
# 1. backing services only
docker compose up -d qdrant redis

# 2. backend
pip install -e ".[dev]"
uvicorn app.api.main:app --reload --port 8090
# interactive API docs (Swagger): http://localhost:8090/docs

# 3. frontend (separate terminal)
cd frontend && npm install && npm run dev    # http://localhost:3003
```

## Seed sample data

With the backend running, load a few cross-referencing sample documents:

```bash
python scripts/seed_sample_data.py            # defaults to http://localhost:8090
```

This creates a **"Sample Knowledge Base"** collection and ingests finance, support, HR, and
security docs — enough to test single-hop and multi-step (agentic) queries. It prints ready-to-run
example queries when it finishes.

## Smoke-test the API

```bash
# health
curl localhost:8090/health
# -> {"status":"ok","version":"0.1.0"}

# ingest text (no LLM key needed — embeddings are local)
curl -X POST localhost:8090/api/v1/rag/documents/text \
  -H 'Content-Type: application/json' \
  -d '{"text":"Acme Q3 revenue was $5M, up 20% YoY.","metadata":{"source":"manual","title":"Q3"}}'

# query (NEEDS an LLM key) — hybrid retrieval + synthesis
curl -X POST localhost:8090/api/v1/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"What was Q3 revenue?","top_k":5}'

# agentic (multi-step) query — includes a "steps" reasoning trace
curl -X POST localhost:8090/api/v1/rag/agent \
  -H 'Content-Type: application/json' \
  -d '{"question":"How did revenue change across quarters?","max_steps":3}'

# collections
curl localhost:8090/api/v1/rag/collections
```

Or drive every endpoint from the Swagger UI at http://localhost:8090/docs.

## Walk the UI

Each step verifies a feature area:

1. **Upload** (`/ingest`) — paste text or drop a `.md` / `.pdf` / `.docx` / `.html` / `.csv`
   file, pick a **Collection**, and ingest.
2. **Query Studio** (`/query`) — ask a question; check the **answer**, **Citations**, and
   **Sources** tabs. Tick **"Agentic (multi-step)"** to see the **reasoning chain** card.
3. **Collections** (`/collections`) — document/chunk **counts** populate after ingesting into a
   collection; create and delete collections.
4. **Copilot** — the floating button (bottom-right on every page) opens a chat with cited
   answers and quick-action shortcuts.
5. **Ollama fallback** — set an invalid `OPENAI_API_KEY`, run a local `ollama serve` with
   `OLLAMA_MODEL` pulled, and confirm a query still answers via Ollama.

## Expected behaviour & gotchas

- **First query is slow** (model download), then fast.
- **Query/agent without an LLM key → HTTP 500.** Ingestion and the retrieval half still work;
  only answer *generation* needs the LLM.
- **Empty knowledge base** → query returns "I don't have enough information to answer that"
  with `low` confidence. Ingest (or seed) first.
- **Upgraded from an early build?** The Qdrant collection schema changed to named
  `dense`+`sparse` vectors (hybrid search). Drop the old collection and re-ingest:
  `curl -X DELETE localhost:6333/collections/dclaw_docs`.
