from app.generation.synthesis import verify_answer


class _LLM:
    def __init__(self, response):
        self.response = response

    async def complete(self, messages, temperature=0.2):
        return self.response


async def test_verify_grounded():
    faith, claims = await verify_answer(
        "answer", [], _LLM('{"faithfulness": "grounded", "unsupported_claims": []}')
    )
    assert faith == "grounded"
    assert claims == []


async def test_verify_partial_with_trailing_prose():
    # tolerate prose after the JSON (small models do this)
    faith, claims = await verify_answer(
        "answer",
        [],
        _LLM('{"faithfulness": "partial", "unsupported_claims": ["X"]}\n\nNote: ...'),
    )
    assert faith == "partial"
    assert claims == ["X"]


async def test_verify_grounded_drops_any_claims():
    faith, claims = await verify_answer(
        "answer", [], _LLM('{"faithfulness": "grounded", "unsupported_claims": ["stray"]}')
    )
    assert faith == "grounded"
    assert claims == []  # grounded => claims forced empty


async def test_verify_partial_with_no_claims_normalizes_to_grounded():
    faith, claims = await verify_answer(
        "answer", [], _LLM('{"faithfulness": "partial", "unsupported_claims": []}')
    )
    assert faith == "grounded"
    assert claims == []


async def test_verify_unparseable_fails_open():
    faith, claims = await verify_answer("answer", [], _LLM("sorry, I cannot"))
    assert faith is None
    assert claims == []
