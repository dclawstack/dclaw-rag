async def test_cors_header_present_for_cross_origin_request(client):
    # A browser request from the frontend origin must get an allow-origin header,
    # otherwise the SPA's fetch() calls are blocked.
    resp = await client.get("/health", headers={"Origin": "http://localhost:3003"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3003"


async def test_cors_preflight_allows_post(client):
    resp = await client.options(
        "/api/v1/rag/query",
        headers={
            "Origin": "http://localhost:3003",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3003"
    assert "POST" in resp.headers.get("access-control-allow-methods", "")
