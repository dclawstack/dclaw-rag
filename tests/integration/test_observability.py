import app.api.routes.health as health_module

# --- metrics ---


async def test_metrics_endpoint_exposes_prometheus(client):
    await client.get("/health")  # generate at least one HTTP metric sample
    resp = await client.get("/metrics")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "http_requests_total" in body
    assert "rag_queries_total" in body


# --- request id ---


async def test_request_id_header_is_set(client):
    resp = await client.get("/health")
    assert resp.headers.get("X-Request-ID")


async def test_request_id_is_echoed_when_provided(client):
    resp = await client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert resp.headers["X-Request-ID"] == "trace-123"


# --- readiness ---


async def test_ready_returns_200_when_deps_up(client, monkeypatch):
    monkeypatch.setattr(health_module, "_check_kv", lambda: True)
    monkeypatch.setattr(health_module, "_check_qdrant", lambda: True)

    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"redis": True, "qdrant": True}


async def test_ready_returns_503_when_a_dep_is_down(client, monkeypatch):
    monkeypatch.setattr(health_module, "_check_kv", lambda: True)
    monkeypatch.setattr(health_module, "_check_qdrant", lambda: False)

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not ready"
