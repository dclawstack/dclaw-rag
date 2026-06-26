async def test_system_info_returns_config(client):
    resp = await client.get("/api/v1/rag/system")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "version",
        "backend_port",
        "vector_store",
        "embedding_model",
        "reranker_model",
        "llm_provider",
        "llm_model",
    ):
        assert key in body, f"missing key: {key}"
    assert body["vector_store"] == "Qdrant"
    assert body["backend_port"] == 8090
    assert body["embedding_model"]
    assert body["llm_provider"]
    assert body["llm_model"]
