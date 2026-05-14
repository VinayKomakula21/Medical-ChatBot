"""Shared helpers for eval runners.

Keeps `ragas_runner.py` and `retrieval_runner.py` independent of each other
while sharing dataset loading, retrieval, generation, and report formatting.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import requests

from app.core.config import settings
from app.services.chat_groq import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def load_dataset_rows(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load JSONL eval rows. Returns [] if file missing."""
    p = Path(path)
    if not p.exists():
        logger.warning("Dataset not found: %s", p)
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    logger.info("Loaded %d rows from %s", len(rows), p)
    return rows


# Module-level override so the embedding-comparison orchestrator can swap in a
# Chroma retriever for a single run without touching the runners themselves.
# When None, retrieve_contexts() uses the production Pinecone path.
_active_retriever: Any = None


def set_active_retriever(retriever: Any) -> None:
    """Override the retriever used by retrieve_contexts() for this process.

    Pass None to revert to the default Pinecone path.
    """
    global _active_retriever
    _active_retriever = retriever


def retrieve_contexts(question: str, k: int = 5) -> list[dict[str, Any]]:
    """Retrieve contexts for an eval row.

    Default: pure vector search via Pinecone (production path). When
    `set_active_retriever(...)` has been called this run, that retriever is
    used instead — used by the embedding-comparison orchestrator to point
    eval runs at ChromaDB collections seeded with different embedding models.

    We intentionally call `search_similar_documents` directly rather than the
    HybridSearchService.search wrapper — the BM25 component requires an
    in-memory index built at server start, which isn't available in offline
    eval runs. Once a "rebuild BM25 from Pinecone" path exists, swap this in.
    """
    if _active_retriever is not None:
        try:
            return _active_retriever.search(query=question, k=k) or []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Active retriever (%s) failed for %r: %s",
                getattr(_active_retriever, "name", "?"), question[:60], exc,
            )
            return []

    from app.db.pinecone import search_similar_documents

    try:
        results = search_similar_documents(query=question, k=k)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Retrieval failed for %r: %s", question[:60], exc)
        return []
    return results or []


def generate_answer_with_groq(
    question: str,
    retrieved_chunks: list[dict[str, Any]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 500,
    timeout: float = 30.0,
) -> str:
    """Mirror GroqChatService._generate_with_groq prompt shape, no DB/cache.

    Uses the same SYSTEM_PROMPT and citation-numbered context layout that
    production uses (`[1]`, `[2]`, …) so eval scores reflect real prompt
    behavior, not an idealized one.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for eval runs.")

    context_parts: list[str] = []
    for i, chunk in enumerate(retrieved_chunks[:5], start=1):
        content = (chunk.get("content") or "")[:400]
        context_parts.append(f"[{i}] {content}")
    context = "\n\n".join(context_parts)

    user_content_parts: list[str] = []
    if context.strip():
        user_content_parts.append(f"**Retrieved medical information:**\n{context[:1600]}\n")
    user_content_parts.append(f"**Question:** {question}")
    user_content = "\n".join(user_content_parts)

    payload = {
        "model": "llama-3.1-8b-instant",  # match production
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 0.9,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    # Soft throttle for free-tier 30 req/min.
    time.sleep(0.2)

    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Groq request failed: %s", exc)
        return ""

    if resp.status_code == 429:
        # Back off once for rate-limit, then retry.
        logger.warning("Groq 429 — backing off 5s then retrying once.")
        time.sleep(5.0)
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)

    if resp.status_code != 200:
        logger.warning("Groq %d: %s", resp.status_code, resp.text[:200])
        return ""

    return resp.json()["choices"][0]["message"]["content"]


def aggregate_by_category(
    per_row: list[dict[str, Any]], metric_cols: list[str]
) -> dict[str, dict[str, float]]:
    """Group per-row scores by category, return {category: {metric: mean}}."""
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in per_row:
        cat = row.get("category", "general")
        for m in metric_cols:
            v = row.get(m)
            if isinstance(v, (int, float)):
                grouped[cat][m].append(float(v))
    return {
        cat: {m: round(mean(vs), 4) for m, vs in metrics.items() if vs}
        for cat, metrics in grouped.items()
    }


def _passes(metric: str, score: float | None, payload: dict[str, Any]) -> str:
    if score is None:
        return "—"
    thresholds = payload.get("thresholds", {})
    if metric not in thresholds:
        return "—"
    return "✅" if score >= thresholds[metric] else "❌"


def write_markdown_report(
    path: Path, payload: dict[str, Any], *, kind: str, timestamp: str
) -> None:
    """Render the human-readable summary at eval/reports/latest.md."""
    aggregates = payload.get("aggregates", {})
    by_category = payload.get("by_category", {})
    n_rows = payload.get("n_rows", 0)
    elapsed = payload.get("elapsed_seconds")
    judge = payload.get("judge_model")
    embedding = payload.get("embedding_model")

    lines: list[str] = []
    lines.append(f"# Eval report — {kind}")
    lines.append("")
    lines.append(f"- Timestamp: `{timestamp}`")
    lines.append(f"- Rows: **{n_rows}**")
    if elapsed is not None:
        lines.append(f"- Wall clock: **{elapsed}s**")
    if judge:
        lines.append(f"- LLM judge: `{judge}` (Groq, free tier)")
    if embedding:
        lines.append(f"- Embedding model: `{embedding}` (local, free)")
    lines.append("")

    lines.append("## Aggregates")
    lines.append("")
    lines.append("| metric | score | threshold | pass |")
    lines.append("|---|---:|---:|:---:|")
    for metric, score in aggregates.items():
        threshold = payload.get("thresholds", {}).get(metric, "—")
        score_str = f"{score:.4f}" if isinstance(score, float) else "—"
        thr_str = f"{threshold:.2f}" if isinstance(threshold, float) else str(threshold)
        lines.append(f"| {metric} | {score_str} | {thr_str} | {_passes(metric, score, payload)} |")
    lines.append("")

    if by_category:
        lines.append("## By category")
        lines.append("")
        all_metrics = sorted({m for cat in by_category.values() for m in cat})
        header = "| category | " + " | ".join(all_metrics) + " |"
        sep = "|---|" + "|".join(["---:"] * len(all_metrics)) + "|"
        lines.append(header)
        lines.append(sep)
        for cat, metrics in sorted(by_category.items()):
            row = [cat] + [
                (f"{metrics[m]:.4f}" if m in metrics else "—") for m in all_metrics
            ]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
