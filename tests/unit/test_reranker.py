"""Unit tests for app.services.reranker.

Covers:
  - NoopReranker passthrough semantics
  - get_reranker() factory respects settings.RERANKER_PROVIDER
  - JinaReranker with a mocked httpx transport (no live API call)
  - JinaReranker degrades gracefully on transport / status / shape failures
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.services import reranker as reranker_mod
from app.services.reranker import JinaReranker, NoopReranker, get_reranker


def _reset_cached_factory() -> None:
    reranker_mod._cached = None


# ---------------------------------------------------------------------------
# NoopReranker
# ---------------------------------------------------------------------------
class TestNoopReranker:
    def test_returns_top_k_in_input_order(self) -> None:
        r = NoopReranker()
        candidates = [{"id": f"c{i}", "content": f"text {i}"} for i in range(8)]
        out = r.rerank("query", candidates, top_k=3)
        assert [c["id"] for c in out] == ["c0", "c1", "c2"]

    def test_empty_input_returns_empty(self) -> None:
        assert NoopReranker().rerank("q", [], top_k=5) == []

    def test_top_k_larger_than_candidates_returns_all(self) -> None:
        cs = [{"id": "x"}, {"id": "y"}]
        assert NoopReranker().rerank("q", cs, top_k=50) == cs


# ---------------------------------------------------------------------------
# get_reranker() factory
# ---------------------------------------------------------------------------
class TestFactory:
    def test_none_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_cached_factory()
        monkeypatch.setattr(reranker_mod.settings, "RERANKER_PROVIDER", "none")
        assert isinstance(get_reranker(), NoopReranker)

    def test_unknown_provider_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_cached_factory()
        monkeypatch.setattr(reranker_mod.settings, "RERANKER_PROVIDER", "made-up")
        assert isinstance(get_reranker(), NoopReranker)

    def test_jina_without_key_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_cached_factory()
        monkeypatch.setattr(reranker_mod.settings, "RERANKER_PROVIDER", "jina")
        monkeypatch.setattr(reranker_mod.settings, "JINA_API_KEY", None)
        assert isinstance(get_reranker(), NoopReranker)


# ---------------------------------------------------------------------------
# JinaReranker — mocked httpx transport so we don't hit jina.ai
# ---------------------------------------------------------------------------
def _mock_jina_client(payload: dict[str, Any] | None, status: int = 200) -> JinaReranker:
    """Build a JinaReranker whose internal httpx.Client uses MockTransport."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.dumps(payload) if payload is not None else "not-json-at-all"
        return httpx.Response(status, content=body.encode())

    r = JinaReranker(api_key="test-key", model="test-model")
    # Replace the live client with one wired to our handler.
    r._client = httpx.Client(transport=httpx.MockTransport(handler))
    return r


class TestJinaReranker:
    def test_happy_path_reorders_by_index(self) -> None:
        # Jina returns indexes into the original candidates list, each with
        # a relevance_score. We expect the reranker to reorder accordingly.
        payload = {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.50},
            ]
        }
        rr = _mock_jina_client(payload)
        cands = [
            {"id": "a", "content": "alpha"},
            {"id": "b", "content": "beta"},
            {"id": "c", "content": "gamma"},
        ]
        out = rr.rerank("query", cands, top_k=2)
        assert [c["id"] for c in out] == ["c", "a"]
        assert out[0]["rerank_score"] == pytest.approx(0.95)
        assert out[1]["rerank_score"] == pytest.approx(0.50)

    def test_passes_through_on_non_200(self) -> None:
        rr = _mock_jina_client({"results": []}, status=500)
        cands = [{"id": "x", "content": "y"}]
        out = rr.rerank("q", cands, top_k=5)
        assert out == cands

    def test_passes_through_on_invalid_json(self) -> None:
        rr = _mock_jina_client(payload=None, status=200)  # body is non-JSON
        cands = [{"id": "x", "content": "y"}]
        out = rr.rerank("q", cands, top_k=5)
        assert out == cands

    def test_empty_results_array_passes_through(self) -> None:
        rr = _mock_jina_client({"results": []}, status=200)
        cands = [{"id": "x", "content": "y"}, {"id": "z", "content": "w"}]
        out = rr.rerank("q", cands, top_k=5)
        # When jina returns empty, we keep original order sliced to top_k.
        assert out == cands

    def test_empty_input_is_short_circuited(self) -> None:
        # No HTTP call should fire when there's nothing to rerank.
        called = {"n": 0}

        def handler(_: httpx.Request) -> httpx.Response:
            called["n"] += 1
            return httpx.Response(200, content=b'{"results":[]}')

        rr = JinaReranker(api_key="k", model="m")
        rr._client = httpx.Client(transport=httpx.MockTransport(handler))
        assert rr.rerank("q", [], top_k=5) == []
        assert called["n"] == 0

    def test_no_api_key_short_circuits_to_passthrough(self) -> None:
        rr = JinaReranker(api_key="", model="m")
        # No HTTP setup needed — should not call the client.
        cands = [{"id": "x", "content": "y"}]
        assert rr.rerank("q", cands, top_k=5) == cands
