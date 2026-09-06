# services/reranker/tests/test_reranker.py
import json
from pathlib import Path
import pytest

from services.reranker.reranker import CrossEncoderReranker
from services.reranker.models import RerankRequest, CandidateChunk

MOCK_DATA_PATH = Path(__file__).parents[3] / "mock-data" / "retrieval_results" / "q1.json"

@pytest.fixture(scope="module")
def reranker():
    return CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")

def load_mock_candidates():
    with open(MOCK_DATA_PATH) as f:
        return json.load(f)["results"]

def test_returns_top_k(reranker):
    raw = load_mock_candidates()
    request = RerankRequest(
        query="What was CTS's finished-goods balance in 2019?",
        candidates=[CandidateChunk(**c) for c in raw],
        top_k=5
    )
    response = reranker.rerank(request)
    assert len(response.reranked) == min(5, len(raw))

def test_sorted_descending(reranker):
    raw = load_mock_candidates()
    request = RerankRequest(
        query="finished-goods balance 2019",
        candidates=[CandidateChunk(**c) for c in raw],
        top_k=10
    )
    response = reranker.rerank(request)
    logits = [r.rerank_logit for r in response.reranked]
    assert logits == sorted(logits, reverse=True)

def test_empty_candidates(reranker):
    request = RerankRequest(query="anything", candidates=[], top_k=5)
    response = reranker.rerank(request)
    assert response.reranked == []

def test_top_k_larger_than_candidates(reranker):
    raw = load_mock_candidates()[:2]
    request = RerankRequest(
        query="anything",
        candidates=[CandidateChunk(**c) for c in raw],
        top_k=100
    )
    response = reranker.rerank(request)
    assert len(response.reranked) == 2

def test_metadata_fields_preserved(reranker):
    raw = load_mock_candidates()
    request = RerankRequest(
        query="anything",
        candidates=[CandidateChunk(**c) for c in raw],
        top_k=5
    )
    response = reranker.rerank(request)

    for r in response.reranked:
        assert "document_id" in r.metadata, f"document_id missing from metadata for {r.chunk_id}"
        assert "page" in r.metadata, f"page missing from metadata for {r.chunk_id}"