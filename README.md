# DCLAW RAG

Retrieval-Augmented Generation (RAG) system for the DCLAW project.

## Quick Start

```bash
# 1. Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# 2. Start infrastructure
docker compose -f infra/docker-compose.yml up -d qdrant redis

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Run API
uvicorn app.api.main:app --reload
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/ingest/file` | Upload and ingest a file |
| POST | `/ingest/text` | Ingest raw text |
| POST | `/query` | Ask a question |

## Project Structure

```
dclaw-rag/
├── app/
│   ├── api/           # FastAPI routes
│   ├── core/          # Config, logging, exceptions
│   ├── ingestion/     # Extractors, chunkers, loaders
│   ├── retrieval/     # Embedder, reranker, search
│   ├── generation/    # LLM gateway, prompts
│   ├── db/            # Qdrant, Redis
│   └── models/        # Pydantic schemas
├── scripts/           # CLI utilities
├── tests/             # Unit & integration tests
├── infra/             # Docker Compose, K8s manifests
└── notebooks/         # Evaluation notebooks
```

## Development

```bash
# Run linting
ruff check app/
mypy app/

# Run tests
pytest tests/
```

## License

Private — DCLAW project.
