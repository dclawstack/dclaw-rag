---
tags: [meta, prd, revised, swarm]
version: 2.3
date: 2026-05-16
app_id: rag
app_name: DClaw RAG
category: Platform
status: P0
---

# 📘 DClaw RAG — Revised PRD v2.3

> **The single document every agent must read before writing code for this app.**
> Generated from DClaw Master PRD v2.2. Read the Master PRD first: https://raw.githubusercontent.com/dclawstack/dclaw-prd/main/DClaw-Master-PRD.md

---

## 1. Product Identity

| Field | Value |
|-------|-------|
| **App ID** | `rag` |
| **Name** | DClaw RAG |
| **Category** | Platform |
| **Tagline** | Universal knowledge retrieval |
| **Color** | #F59E0B |
| **Phase** | P0 |
| **Port (Frontend Dev)** | 3008 (Assigned) |
| **Port (Backend Dev)** | 8090 (Assigned) |
| **Maturity Tier** | 🟢 Tier 1 — Mature |

---

## 2. Current State Assessment

### 2.1 Scaffold Status
| Component | Status | Notes |
|-----------|--------|-------|
| `frontend/` | ✅ | Next.js 14+ app |
| `backend/` | ❌ | FastAPI + SQLAlchemy 2.0 |
| `docs/` | ✅ | getting-started, guides, reference, releases |
| `helm/` | ✅ | K8s deployment manifests |
| `.github/workflows/` | ✅ | CI/CD + Claude integration |
| `AGENTS.md` | ✅ | Per-repo agent instructions |
| `PLAN-v1.2.md` | ✅ | Feature roadmap |
| `docker-compose.yml` | ✅ | Local dev stack |
| `tests/` | ✅ | pytest + pytest-asyncio |
| `alembic/` | ❌ | Database migrations |
| `dclaw-manifest.json` | ✅ | DPanel registration |

### 2.2 Code Maturity
| Metric | Value |
|--------|-------|
| Python source files (backend) | ~41 |
| TypeScript/TSX files (frontend) | ~27 |
| Total source files | ~68 |
| Tests | ✅ Present |
| Alembic migrations | ❌ Missing |
| DPanel manifest | ✅ Present |

### 2.3 Feature Maturity
- **P0 Foundation:** Partially implemented
- **P1 Platform:** Not yet started
- **P2 Vertical:** Not yet started

---

## 3. Gap Analysis

| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| 1 | Missing `backend/` directory | 🔴 | Scaffold FastAPI backend with SQLAlchemy 2.0 |
| 2 | Missing Alembic migrations | 🟡 | Initialize alembic and create initial migration |
| 3 | Backend at repo root instead of `backend/` — breaks canonical structure | 🔴 | Restructure into backend/ + frontend/ or document exception |

---

## 4. Sacred Architecture & Tech Stack

> **NON-NEGOTIABLE. Every DClaw product MUST use this exact stack.**

| Layer | Technology | Version |
|-------|------------|---------|
| **Frontend** | Next.js 14+ | App Router, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI | Pydantic v2, SQLAlchemy 2.0, asyncpg |
| **Database** | PostgreSQL 16 | CloudNativePG operator in K8s |
| **Vector DB** | Qdrant / pgvector | Only if RAG / semantic search |
| **Cache / Bus** | Redis | 7.x |
| **Object Storage** | MinIO | Latest |
| **Workflow** | Temporal.io | Only if automation/orchestration |
| **Auth** | Logto | JWT validation on all protected routes |
| **Billing** | Stripe | Metered or per-seat |
| **K8s Operator** | Go + controller-runtime | 0.18 |
| **LLM Local** | Ollama | Apple Silicon |
| **LLM Cloud** | OpenRouter + Kimi K2.5 | Fallback |
| **Monitoring** | Prometheus + Grafana | Latest |

### 4.1 Python Rules
- `ruff` formatting enforced
- Type hints on ALL public APIs
- `pydantic` v2 for schemas
- `sqlalchemy` 2.0 style (`Mapped`, `mapped_column`)
- `pytest` + `pytest-asyncio` for tests
- Functions < 50 lines
- No `print()` — use `structlog`

### 4.2 TypeScript / Next.js Rules
- Strict TypeScript (`strict: true`)
- Tailwind for ALL styling
- `cn()` utility for conditional classes
- No `any` without `// @ts-ignore`

### 4.3 Docker Standards
- Port mappings MUST match container listen port
- Healthchecks MUST use binaries present in base image
- `docker compose config` must pass before shipping
- Service type MUST be `ClusterIP`
- TLS required on all ingress

---

## 5. P0 Foundation Features (Must Have — Demo Ready)

> **Every P0 MUST include an AI Copilot per YC S25/W26 RFS.**

| # | Feature | Description | AI Component | Acceptance Criteria |
|---|---------|-------------|--------------|---------------------|
| P0.1 | **AI RAG Copilot** | Ask questions in natural language; get answers from your knowledge base. | Hybrid search + reranking + LLM synthesis | Answer accuracy >85%; cite sources; latency <3s |
| P0.2 | **Multi-Format Ingestion** | Ingest PDFs, Word, web pages, databases, and APIs. | AI document-parsing + chunking strategy | Support 15+ formats; auto-chunking; metadata extraction |
| P0.3 | **Hybrid Search & Reranking** | Combine vector, keyword, and semantic search for best results. | Cross-encoder reranking + query expansion | BM25 + dense retrieval; rerank top 100; MRR >0.8 |
| P0.4 | **Agentic RAG** | Agents that autonomously search, synthesize, and answer complex queries. | Multi-step reasoning + tool-use + source verification | Handle 5-step queries; verify facts against 3+ sources |

---

## 6. P1 Platform Features (Should Have — v1.1–1.2)

| # | Feature | Description | AI Component | Acceptance Criteria |
|---|---------|-------------|--------------|---------------------|
| P1.1 | **Knowledge Graph** | Build entity-relationship graphs from ingested documents. | AI entity-extraction + relation-inference | Extract 50+ entity types; visualize graph; query via Cypher |
| P1.2 | **Auto-Sync Connectors** | Keep knowledge base in sync with Google Drive, Confluence, Notion. | AI change-detection + incremental indexing | Sync every 15min; delta updates; conflict resolution |
| P1.3 | **Analytics Dashboard** | Track queries, satisfaction, and knowledge gaps. | AI unanswered-question clustering + content-gap identification | Track 20+ metrics; identify top 10 knowledge gaps |
| P1.4 | **Access Control** | Document-level permissions with RBAC. | AI sensitivity-classification + auto-redaction | Role-based access; auto-classify PII; audit logs |

---

## 7. P2 Vertical / Scale Features (Could Have — v1.3+)

| # | Feature | Description | AI Component | Acceptance Criteria |
|---|---------|-------------|--------------|---------------------|
| P2.1 | **Collaborative Annotations** | Highlight, comment, and tag knowledge base entries. | AI annotation-summarization + consensus detection | Threaded annotations; tags; export to report |
| P2.2 | **White-Label Embed** | Embed RAG search widget into any website or app. | AI branding-adaptation + customization | IFrame embed; custom styling; webhook search events |
| P2.3 | **Multi-Tenant Isolation** | Isolate knowledge bases per organization with shared infrastructure. | AI resource-quota optimization | Namespace isolation; per-tenant Qdrant collections |
| P2.4 | **LLM Evaluation** | Benchmark RAG performance with automated test suites. | AI evaluation-metric suggestion + regression detection | Answer relevance; faithfulness; latency; run nightly |

---

## 8. Scaffold Checklist

Before marking this app "shipped", confirm:

- [ ] `frontend/` with Next.js 14+, Tailwind, shadcn/ui
- [ ] `backend/` with FastAPI, Pydantic v2, SQLAlchemy 2.0, asyncpg
- [ ] `docs/` with getting-started, guides, reference, releases, troubleshooting
- [ ] `helm/` with Chart.yaml, values.yaml, templates (deployment, service, ingress, cloudnativepg)
- [ ] `.github/workflows/` with build-backend.yml, build-frontend.yml, deploy.yml, claude.yml
- [ ] `frontend/public/dclaw-manifest.json` for DPanel registration
- [ ] `backend/tests/` with pytest + pytest-asyncio
- [ ] `backend/alembic/` with initial migration
- [ ] `Dockerfile` + `docker-compose.yml` with correct healthchecks
- [ ] Health endpoint at `/health` returning `{"status":"ok"}`
- [ ] `AGENTS.md` with per-repo instructions
- [ ] `PLAN-v1.2.md` with feature roadmap
- [ ] Port assigned from registry and documented
- [ ] No hardcoded secrets — use `.env.example` + K8s Secrets
- [ ] Non-root containers in Dockerfile

---

## 9. AI Copilot Mandate (YC S25/W26 Requirement)

Every DClaw app MUST have an AI Copilot as its first P0 feature. The copilot must:
1. Be contextually aware of the app's domain data
2. Use RAG over the app's knowledge base where applicable
3. Suggest next actions, not just answer questions
4. Be accessible from every page via floating chat or sidebar
5. Fall back to local Ollama when cloud is unavailable

---

## 10. Next Tasks for Vibe Coders

1. **Complete P0 features**: Finish any incomplete P0 backend services and frontend pages.
2. **Add missing scaffold**: Fill gaps identified above (docs, helm, tests, manifest, etc.).
3. **Start P1 features**: Implement the first 2 P1 features to deepen domain capability.
4. **Polish and integrate**: Ensure health endpoints, Docker builds, and DPanel manifest are production-ready.

---

## 11. Domain Research Notes

Inspired by Glean, Perplexity, Azure AI Search, Pinecone. RAG is the killer app for enterprise knowledge.

---

## 12. Links & Resources

| Resource | URL |
|----------|-----|
| **Master PRD** | https://raw.githubusercontent.com/dclawstack/dclaw-prd/main/DClaw-Master-PRD.md |
| **GitHub Org** | https://github.com/dclawstack |
| **DPanel** | https://dpanel.dclawstack.io |
| **Port Registry** | See `dclaw-platform/PORT_REGISTRY.md` |
| **App PRD Template** | Obsidian Vault → `00-META/📐 App PRD Template.md` |
| **Scaffold Source** | `dclaw-scaffold/` in DClaw-Stack |

---

*Revised PRD version: 2.3*
*Generated: 2026-05-16 by DClaw Stack Generator*
*Next review: When P0 features are complete or architecture changes*
