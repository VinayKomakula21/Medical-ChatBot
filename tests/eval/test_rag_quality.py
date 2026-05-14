"""RAG-quality smoke tests gated on threshold scores.

Marked `@pytest.mark.slow` because they:
  - hit live Pinecone for retrieval
  - hit live Groq for generation (in the RAGAS test) and judging

Run explicitly:
    pytest -m slow tests/eval/

These are designed for CI gating — if a future change drops faithfulness or
hit@5 below the configured threshold, the test fails loud with the actual
number so the regression is immediately visible.
"""
from __future__ import annotations

import os

import pytest

from app.core.config import settings


@pytest.mark.slow
def test_hit_at_5_meets_threshold() -> None:
    """Retrieval finds a relevant chunk in the top-5 for the smoke set."""
    if not os.environ.get("PINECONE_API_KEY") and not settings.PINECONE_API_KEY:
        pytest.skip("PINECONE_API_KEY not configured")

    from eval.runners._common import load_dataset_rows
    from eval.runners.retrieval_runner import _evaluate

    rows = load_dataset_rows(settings.EVAL_SMOKE_DATASET_PATH)
    assert rows, f"Smoke dataset missing at {settings.EVAL_SMOKE_DATASET_PATH}"

    payload = _evaluate(rows, k=5)
    score = payload["aggregates"]["hit_at_5"]
    threshold = settings.EVAL_HIT_AT_5_THRESHOLD
    assert score >= threshold, (
        f"hit@5 regressed: {score:.3f} < {threshold:.2f} "
        f"(see {settings.EVAL_REPORTS_DIR}/latest.md)"
    )


@pytest.mark.slow
def test_faithfulness_meets_threshold() -> None:
    """RAGAS faithfulness on the smoke set stays above the configured floor."""
    if not settings.GROQ_API_KEY:
        pytest.skip("GROQ_API_KEY not configured (RAGAS judge needs it)")

    from eval.runners._common import load_dataset_rows
    from eval.runners.ragas_runner import _evaluate

    rows = load_dataset_rows(settings.EVAL_SMOKE_DATASET_PATH)
    assert rows, f"Smoke dataset missing at {settings.EVAL_SMOKE_DATASET_PATH}"

    payload = _evaluate(rows)
    score = payload["aggregates"].get("faithfulness")
    threshold = settings.EVAL_FAITHFULNESS_THRESHOLD
    assert score is not None, "RAGAS did not produce a faithfulness score"
    assert score >= threshold, (
        f"faithfulness regressed: {score:.3f} < {threshold:.2f} "
        f"(see {settings.EVAL_REPORTS_DIR}/latest.md)"
    )


@pytest.mark.slow
def test_context_precision_meets_threshold() -> None:
    """RAGAS context_precision on the smoke set stays above floor."""
    if not settings.GROQ_API_KEY:
        pytest.skip("GROQ_API_KEY not configured (RAGAS judge needs it)")

    from eval.runners._common import load_dataset_rows
    from eval.runners.ragas_runner import _evaluate

    rows = load_dataset_rows(settings.EVAL_SMOKE_DATASET_PATH)
    payload = _evaluate(rows)
    score = payload["aggregates"].get("context_precision")
    threshold = settings.EVAL_CONTEXT_PRECISION_THRESHOLD
    assert score is not None, "RAGAS did not produce a context_precision score"
    assert score >= threshold, (
        f"context_precision regressed: {score:.3f} < {threshold:.2f} "
        f"(see {settings.EVAL_REPORTS_DIR}/latest.md)"
    )
