"""Eval depth (E4.12): the versioned adversarial set is well-formed and the
history writer appends valid JSON lines."""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADVERSARIAL = REPO / "eval" / "adversarial_set.json"
GOLDEN = REPO / "eval" / "golden_set.json"


def _load_evaluate_module():
    spec = importlib.util.spec_from_file_location(
        "evaluate_script", REPO / "scripts" / "evaluate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", [ADVERSARIAL, GOLDEN])
def test_eval_dataset_is_well_formed(path):
    data = json.loads(path.read_text())
    for key in ("corpus", "answerable", "unanswerable"):
        assert isinstance(data[key], list) and data[key], f"{path.name}:{key}"

    sources = {doc["source"] for doc in data["corpus"]}
    for item in data["answerable"]:
        assert {"question", "expected_source", "expected_answer"} <= item.keys()
        # Every expected source must actually be in the corpus (no dangling refs).
        assert item["expected_source"] in sources, item["expected_source"]
    for item in data["unanswerable"]:
        assert "question" in item


def test_adversarial_set_is_versioned():
    data = json.loads(ADVERSARIAL.read_text())
    assert data.get("version"), "adversarial set must carry a version for tracking"


def test_history_append_writes_jsonl(tmp_path):
    module = _load_evaluate_module()
    history = tmp_path / "sub" / "history.jsonl"

    module._append_history(history, {"hit_rate": 0.9, "mrr": 0.8})
    module._append_history(history, {"hit_rate": 1.0, "mrr": 1.0})

    lines = history.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["hit_rate"] == 0.9
    assert json.loads(lines[1])["mrr"] == 1.0
