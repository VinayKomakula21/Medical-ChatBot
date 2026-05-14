"""Unit tests for app.services.hybrid_search.

Focuses on the deterministic internals: tokenizer + reciprocal-rank-fusion.
Full search() integration is covered by the eval/runners, which need live
Pinecone — out of scope here.
"""
from __future__ import annotations

import pytest

from app.services.hybrid_search import HybridSearchService


@pytest.fixture
def svc() -> HybridSearchService:
    # Fresh instance per test — no shared state.
    return HybridSearchService()


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------
class TestTokenize:
    def test_lowercases(self, svc: HybridSearchService) -> None:
        assert "abc" in svc._tokenize("ABC")

    def test_strips_punctuation(self, svc: HybridSearchService) -> None:
        toks = svc._tokenize("Hello, world! This is a test.")
        assert "," not in toks and "!" not in toks
        assert {"hello", "world", "this", "is", "a", "test"} <= set(toks)

    def test_handles_empty_string(self, svc: HybridSearchService) -> None:
        assert svc._tokenize("") == []

    def test_splits_on_whitespace(self, svc: HybridSearchService) -> None:
        # Multi-whitespace handled, no empty tokens.
        toks = svc._tokenize("foo   bar\tbaz\nqux")
        assert toks == ["foo", "bar", "baz", "qux"]


# ---------------------------------------------------------------------------
# _reciprocal_rank_fusion
# Verifies the published RRF formula (1 / (k + rank)) and merge semantics.
# ---------------------------------------------------------------------------
class TestRRF:
    def _docs(self) -> list[dict]:
        return [
            {"id": "d1", "content": "doc one"},
            {"id": "d2", "content": "doc two"},
            {"id": "d3", "content": "doc three"},
        ]

    def test_returns_empty_when_both_lists_empty(self, svc: HybridSearchService) -> None:
        out = svc._reciprocal_rank_fusion(vector_results=[], bm25_results=[], k=60)
        assert out == []

    def test_vector_only_preserves_order(self, svc: HybridSearchService) -> None:
        vec = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        out = svc._reciprocal_rank_fusion(vec, [], k=60)
        assert [r["id"] for r in out] == ["a", "b", "c"]
        # Higher rank → higher fused score
        assert out[0]["fused_score"] > out[1]["fused_score"] > out[2]["fused_score"]

    def test_doc_in_both_lists_outranks_either_alone(
        self, svc: HybridSearchService
    ) -> None:
        # Doc "shared" appears mid-pack in both lists. RRF should boost it
        # above any doc that appears in only one list.
        svc.documents = [{"id": "shared", "content": "x"}, {"id": "bm_only", "content": "y"}]
        vec = [{"id": "vec_only"}, {"id": "shared"}]
        bm25 = [(0, 5.0), (1, 3.0)]  # (idx_in_svc.documents, score)
        out = svc._reciprocal_rank_fusion(vec, bm25, k=60)
        # "shared" should rank above both single-source docs.
        ids = [r["id"] for r in out]
        assert ids.index("shared") < ids.index("vec_only")
        assert ids.index("shared") < ids.index("bm_only")

    def test_fused_score_uses_rank_one_based(self, svc: HybridSearchService) -> None:
        # Confirm the formula: 1 / (k + rank + 1)
        vec = [{"id": "x"}]
        out = svc._reciprocal_rank_fusion(vec, [], k=60)
        expected = 1.0 / (60 + 0 + 1)  # rank 0 → 1/61
        assert out[0]["fused_score"] == pytest.approx(expected)
