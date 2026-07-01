import { clearToken, getToken, refreshAccessToken } from "./auth";
import { API_BASE, API_KEY } from "./tokens";

// Prefer the logged-in user's JWT; fall back to the dev API key if configured.
const authHeaders = (): Record<string, string> => {
  const token = getToken() || API_KEY;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

function redirectToLogin() {
  clearToken();
  if (typeof window !== "undefined") window.location.href = "/login";
}

export interface ChunkMetadata {
  source?: string;
  title?: string;
  [key: string]: string | number | boolean | null | undefined;
}

export interface QueryResponse {
  query: string;
  answer: string;
  results: Array<{
    chunk_id: string;
    score: number;
    text: string;
    document_name: string;
    metadata: ChunkMetadata;
  }>;
  retrieved_chunks: Array<{
    id: string;
    chunk_id: string;
    score: number;
    text: string;
    document_name: string;
    metadata: ChunkMetadata;
  }>;
  citations: Array<{
    index: number;
    chunk_id: string;
    text: string;
    source: string;
    page?: number;
  }>;
  confidence: "high" | "medium" | "low";
  abstained?: boolean;
  faithfulness?: "grounded" | "partial" | "unsupported" | null;
  unsupported_claims?: string[];
  latency_ms: number;
}

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  chunk_count: number;
  status: string;
  tags: string[];
  created_at: string;
}

export interface Document {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  chunk_count: number;
  error: string | null;
}

async function apiFetch(path: string, options?: RequestInit, retried = false) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options?.headers,
    },
  });
  if (res.status === 401 && !retried) {
    // access token likely expired — try a silent refresh, then retry once
    if (await refreshAccessToken()) return apiFetch(path, options, true);
    redirectToLogin();
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function healthCheck(): Promise<{ status: string; version?: string }> {
  return apiFetch("/health");
}

export interface SystemInfo {
  version: string;
  backend_port: number;
  vector_store: string;
  embedding_model: string;
  reranker_model: string;
  llm_provider: string;
  llm_model: string;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  return apiFetch("/api/v1/rag/system");
}

export interface Stats {
  collections: number;
  documents: number;
  chunks: number;
}

export async function getStats(): Promise<Stats> {
  return apiFetch("/api/v1/rag/stats");
}

export async function queryRag(params: {
  question: string;
  top_k: number;
  collection_id?: string;
  verify?: boolean;
}): Promise<QueryResponse> {
  return apiFetch(`/api/v1/rag/query`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface AgentStep {
  sub_question: string;
  n_results: number;
}

export interface AgentResponse {
  query: string;
  answer: string;
  citations: QueryResponse["citations"];
  retrieved_chunks: QueryResponse["retrieved_chunks"];
  confidence: "high" | "medium" | "low";
  steps: AgentStep[];
  latency_ms: number;
}

export async function agentQuery(params: {
  question: string;
  top_k: number;
  collection_id?: string;
  max_steps?: number;
}): Promise<AgentResponse> {
  return apiFetch(`/api/v1/rag/agent`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function ingestFile(
  file: File,
  metadata?: Record<string, unknown>,
  retried = false
) {
  const formData = new FormData();
  formData.append("file", file);
  if (metadata) formData.append("metadata", JSON.stringify(metadata));

  const res = await fetch(`${API_BASE}/api/v1/rag/documents/upload`, {
    method: "POST",
    body: formData,
    headers: authHeaders(),
  });
  if (res.status === 401 && !retried) {
    if (await refreshAccessToken()) return ingestFile(file, metadata, true);
    redirectToLogin();
  }
  if (!res.ok) throw new Error(`Upload error: ${res.status}`);
  return res.json();
}

export async function ingestText(
  text: string,
  metadata?: Record<string, unknown>
) {
  return apiFetch(`/api/v1/rag/documents/text`, {
    method: "POST",
    body: JSON.stringify({ text, metadata }),
  });
}

export async function getCollections(): Promise<Collection[]> {
  return apiFetch("/api/v1/rag/collections");
}

export const listCollections = getCollections;

export async function createCollection(data: {
  name: string;
  description?: string;
}): Promise<Collection> {
  return apiFetch("/api/v1/rag/collections", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteCollection(id: string): Promise<void> {
  await apiFetch(`/api/v1/rag/collections/${id}`, { method: "DELETE" });
}

export async function getDocuments(collectionId: string): Promise<Document[]> {
  return apiFetch(`/api/v1/rag/collections/${collectionId}/documents`);
}

export async function getDocument(docId: string): Promise<Document> {
  return apiFetch(`/api/v1/rag/documents/${docId}`);
}
