from app.models.schemas import QueryResponse, TextIngestRequest


def test_query_response_confidence_defaults_to_medium():
    resp = QueryResponse(
        query="q",
        answer="a",
        results=[],
        retrieved_chunks=[],
        citations=[],
        latency_ms=12.5,
    )
    assert resp.confidence == "medium"
    assert resp.latency_ms == 12.5


def test_text_ingest_request_metadata_defaults_to_empty_dict():
    req = TextIngestRequest(text="hi")
    assert req.metadata == {}
