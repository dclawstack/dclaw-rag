# DClaw RAG — v1.2 Feature Roadmap

> Based on: Y Combinator vertical SaaS principles, trending GitHub repos (langchain, haystack), AI product research (Pinecone, Weaviate, Vercel AI SDK, LlamaIndex)

## Pre-Flight Checklist

- [ ] `frontend/package-lock.json` committed after any `npm install` / dependency change
- [ ] `frontend/next-env.d.ts` exists and is committed
- [ ] `docker-compose.yml` healthchecks correct
- [ ] `frontend/Dockerfile` declares `ARG NEXT_PUBLIC_API_URL` before `RUN npm run build`

## v1.0 Feature Inventory (Current)

- [ ] Document ingestion pipeline
- [ ] Vector store integration
- [ ] Retrieval + generation endpoint
- [ ] Citation tracking
- [ ] Real backend CRUD (no mocks)
- [ ] Docker + Helm deployment
- [ ] Alembic migrations
- [ ] Backend tests

---

## v1.2 Roadmap

### P0 — Must Have (Ship in v1.0, demo-ready)

#### 1. AI RAG Copilot (Knowledge Explorer)
**Description:** Advanced RAG interface with source citations, follow-up questions, and multi-document synthesis. "Compare the Q3 revenue across all uploaded earnings reports."
- **AI Angle:** Multi-document RAG with reranking. Citation extraction. Query expansion.
- **Backend:** `/api/v1/ai/rag-chat` endpoint. Hybrid search (dense + sparse).
- **Frontend:** Chat UI with inline citations. Source document viewer with highlight.
- **Files:** `backend/app/services/rag_engine.py`, `frontend/src/components/rag-copilot.tsx`

#### 2. Multi-Format Document Ingestion
**Description:** Ingest PDF, DOCX, Markdown, HTML, CSV, and images. Auto-extract tables and images.
- **Backend:** Ingestion pipeline with OCR (Tesseract/LLaVA). Chunking strategies.
- **Frontend:** Upload dropzone with progress. Document list with parsing status.
- **Files:** `backend/app/services/ingestion.py`

#### 3. Hybrid Search & Reranking
**Description:** Combine vector similarity, keyword BM25, and metadata filtering. Rerank with cross-encoder.
- **Backend:** Hybrid query engine. Reranking service.
- **Frontend:** Search results with relevance scores.
- **Files:** `backend/app/services/search.py`

#### 4. Agentic RAG (Multi-Step Reasoning)
**Description:** RAG agent that plans, retrieves, reasons, and answers complex questions requiring multiple steps.
- **AI Angle:** ReAct / Plan-and-Execute pattern with tool use.
- **Backend:** Agent orchestration with LangGraph.
- **Frontend:** Reasoning chain visualization.
- **Files:** `backend/app/services/agentic_rag.py`

### P1 — Should Have (v1.1–1.2)

#### 5. Knowledge Graph Construction
**Description:** Extract entities and relationships from documents. Build navigable knowledge graph.
- **Backend:** NER + relation extraction pipeline. Graph store (Neo4j).
- **Frontend:** Interactive knowledge graph explorer.

#### 6. Multi-Modal RAG (Images + Video)
**Description:** Search and answer questions about images, diagrams, and video content.
- **AI Angle:** Multi-modal embeddings (CLIP). Video scene indexing.
- **Backend:** Multi-modal vector store.
- **Frontend:** Image search with natural language.

#### 7. Eval & Observability
**Description:** RAG evaluation framework: answer relevance, retrieval accuracy, latency. A/B test prompts.
- **Backend:** Eval pipeline with synthetic test sets.
- **Frontend:** Eval dashboard with metrics over time.

#### 8. API & SDK for Embedded RAG
**Description:** White-label RAG API for other apps to embed. JS/React SDK.
- **Backend:** Multi-tenant API with API keys.
- **Frontend:** Developer portal with API playground.

### P2 — Could Have (v1.3+)

#### 9. Auto-Indexing & Sync
**Description:** Auto-sync with Google Drive, Notion, Confluence, SharePoint.

#### 10. Federated RAG (Multi-Source)
**Description:** Query across multiple vector stores and APIs with unified results.

#### 11. Private LLM Deployment
**Description:** One-click deployment of private LLMs (Llama, Mistral) for air-gapped environments.

#### 12. RAG-Powered Code Intelligence
**Description:** Specialized RAG for codebases: architecture Q&A, dependency analysis, refactoring suggestions.

---

## Implementation Priority

1. **Week 1–2:** AI RAG Copilot (P0.1) + Document Ingestion (P0.2)
2. **Week 3–4:** Hybrid Search (P0.3) + Agentic RAG (P0.4)
3. **Week 5–6:** Knowledge Graph (P1.5) + Multi-Modal RAG (P1.6)
4. **Week 7–8:** Eval Framework (P1.7) + Embedded RAG API (P1.8)
