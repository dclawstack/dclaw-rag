from app.generation.synthesis import parse_answer


def test_parse_clean_json():
    raw = '{"answer": "42", "citations": [1, 2], "confidence": "high"}'
    assert parse_answer(raw) == ("42", [1, 2], "high")


def test_parse_fenced_json():
    raw = '```json\n{"answer": "hi", "citations": [], "confidence": "low"}\n```'
    assert parse_answer(raw) == ("hi", [], "low")


def test_parse_json_with_trailing_prose():
    # the real llama3.2:3b failure mode: valid JSON, then an explanatory note
    raw = (
        '{"answer": "$5.0 million", "citations": [1], "confidence": "high"}\n\n'
        'Note: confidence is high because the figure is explicit in Context[^1^].'
    )
    answer, citations, confidence = parse_answer(raw)
    assert answer == "$5.0 million"
    assert citations == [1]
    assert confidence == "high"


def test_parse_json_with_preamble():
    raw = 'Here is the answer:\n{"answer": "ok", "citations": [3], "confidence": "medium"}'
    assert parse_answer(raw) == ("ok", [3], "medium")


def test_parse_non_json_falls_back_to_raw():
    raw = "I could not find that information."
    answer, citations, confidence = parse_answer(raw)
    assert answer == raw
    assert citations == []
    assert confidence == "medium"
