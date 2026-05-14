"""Rerankers — second-stage scoring after hybrid retrieval.

Why this exists:
  Hybrid (vector + BM25 + RRF) is good at *recall* but mediocre at the *order*
  of top-5. A reranker re-scores top-N candidates with a cross-encoder that
  attends to query+candidate jointly, and tends to lift precision@5 by 10-30%
  with a small (~200ms) latency cost.

Free-tier defaults:
  - Jina API: 10M-token lifetime free grant per key, 100 RPM. Fine for
    portfolio scale. Default model `jina-reranker-v2-base-multilingual`.
    Note: jina-reranker-v3 weights are CC-BY-NC; the API has no such
    restriction in their TOS, but check before commercial use.
  - "noop": passthrough — keeps the project working with no key. Default.
  - "bge" (future): local bge-reranker-v2-m3 via sentence-transformers'
    CrossEncoder. Apache-2.0, commercial-safe, runs on CPU (~300ms).
    Not implemented yet to keep this change focused.

Production wiring lives in HybridSearchService.search — this module just
exposes get_reranker(), which respects settings.RERANKER_PROVIDER.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    """Score a query against N candidate documents, return them re-ordered."""

    name: str

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        """Return at most top_k candidates with `rerank_score` field added,
        sorted desc by rerank_score.
        """
        ...


# ---------------------------------------------------------------------------
# Noop — explicit passthrough; the default when RERANKER_PROVIDER=none.
# ---------------------------------------------------------------------------
class NoopReranker:
    name = "noop"

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        return candidates[:top_k]


# ---------------------------------------------------------------------------
# Jina — free 10M-token grant; SOTA on BEIR per the 2026 leaderboard.
# ---------------------------------------------------------------------------
class JinaReranker:
    """Calls https://api.jina.ai/v1/rerank.

    On failure (network, 4xx, 5xx, empty response) we fall back to the input
    order — the upstream code path stays robust. Errors are logged.
    """

    name = "jina"
    _ENDPOINT = "https://api.jina.ai/v1/rerank"
    _TIMEOUT = 8.0

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.Client(timeout=self._TIMEOUT)

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        if not candidates:
            return []
        if not self._api_key:
            logger.debug("JinaReranker: no API key — passthrough")
            return candidates[:top_k]

        # Jina expects the documents list as plain strings (or {text: ...}).
        documents = [(c.get("content") or "") for c in candidates]
        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": min(top_k, len(documents)),
            "return_documents": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = self._client.post(self._ENDPOINT, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Jina rerank request failed (%s) — passthrough", exc)
            return candidates[:top_k]

        if resp.status_code != 200:
            logger.warning("Jina rerank %d: %s — passthrough", resp.status_code, resp.text[:200])
            return candidates[:top_k]

        try:
            data = resp.json()
            ranked = data.get("results", [])
        except ValueError:
            logger.warning("Jina rerank returned non-JSON — passthrough")
            return candidates[:top_k]

        if not ranked:
            return candidates[:top_k]

        out: list[dict] = []
        for r in ranked:
            idx = r.get("index")
            score = r.get("relevance_score")
            if idx is None or idx >= len(candidates):
                continue
            item = dict(candidates[idx])
            item["rerank_score"] = float(score) if score is not None else None
            out.append(item)
        return out[:top_k]


# ---------------------------------------------------------------------------
# Factory — single entry point for the rest of the app.
# ---------------------------------------------------------------------------
_cached: Reranker | None = None


def get_reranker() -> Reranker:
    """Return the configured reranker singleton.

    Re-reads settings only on first call — restart the process to swap.
    """
    global _cached
    if _cached is not None:
        return _cached

    provider = (settings.RERANKER_PROVIDER or "").strip().lower()

    # Auto-enable Jina when the user has dropped a key in .env but hasn't
    # explicitly set RERANKER_PROVIDER. Keeps "configure once, works" UX.
    if provider in ("", "auto") and settings.JINA_API_KEY:
        provider = "jina"
        logger.info("Reranker: auto-detected JINA_API_KEY → using jina")

    if provider == "jina":
        if not settings.JINA_API_KEY:
            logger.warning("RERANKER_PROVIDER=jina but JINA_API_KEY missing — using noop.")
            _cached = NoopReranker()
        else:
            _cached = JinaReranker(
                api_key=settings.JINA_API_KEY,
                model=settings.JINA_RERANKER_MODEL,
            )
            logger.info("Reranker: jina (%s)", settings.JINA_RERANKER_MODEL)
    elif provider in ("none", "noop", ""):
        _cached = NoopReranker()
    else:
        logger.warning("Unknown RERANKER_PROVIDER=%r — using noop.", provider)
        _cached = NoopReranker()
    return _cached
