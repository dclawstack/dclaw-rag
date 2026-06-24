from uuid import UUID

from app.models.schemas import ChunkMetadata, DocumentChunk
from app.retrieval.search import reciprocal_rank_fusion


def _chunk(n: int) -> DocumentChunk:
    return DocumentChunk(
        id=UUID(int=n),
        text=f"chunk {n}",
        metadata=ChunkMetadata(doc_id=UUID(int=0), chunk_index=n, source="t"),
    )


def test_rrf_dedups_and_demotes_low_consensus():
    a, b, c = _chunk(1), _chunk(2), _chunk(3)
    fused = reciprocal_rank_fusion([[a, b, c], [b, a, c]], k=60)
    ids = [str(x.id) for x in fused]

    assert len(ids) == len(set(ids)) == 3  # deduped across both lists
    assert ids[-1] == str(c.id)  # c is last in both lists -> lowest fused score


def test_rrf_rewards_documents_in_both_lists():
    a, b = _chunk(1), _chunk(2)
    # b ranks first in the dense list, but a appears in both
    fused = reciprocal_rank_fusion([[b, a], [a]], k=60)
    assert str(fused[0].id) == str(a.id)


def test_rrf_empty_input():
    assert reciprocal_rank_fusion([[], []]) == []
