"""Embedding-model 3-way comparison (Item #3 of IMPROVEMENT_PLAN.md).

Indexes the eval corpus (union of all ground_truth_contexts from the dataset)
into three independent ChromaDB collections — one per HF embedding model — and
runs both eval runners against each. Produces a single markdown comparison
report so before/after numbers are visible at a glance.

All free tier:
  - sentence-transformers run locally (no API)
  - ChromaDB in-process (no service)
  - Groq is only used by the RAGAS judge step (same free tier as production)

Usage:
  python -m eval.runners.embedding_compare                  # full dataset
  python -m eval.runners.embedding_compare --smoke          # 5-row smoke set
  python -m eval.runners.embedding_compare --skip-ragas     # retrieval metrics only (fast)
  python -m eval.runners.embedding_compare --models a,b,c   # custom HF model ids

Default models (all free):
  - sentence-transformers/all-MiniLM-L6-v2   (project baseline, 384d, ~90MB)
  - NeuML/pubmedbert-base-embeddings         (medical specialist, 768d, ~440MB)
  - BAAI/bge-large-en-v1.5                   (general SOTA, 1024d, ~1.3GB)

First run downloads each model into ~/.cache/huggingface (one-time disk cost,
~2GB combined). Subsequent runs are cached.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from eval.runners._common import (
    load_dataset_rows,
    set_active_retriever,
)
from eval.runners._retrievers import ChromaRetriever, _slugify

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "NeuML/pubmedbert-base-embeddings",
    "BAAI/bge-large-en-v1.5",
]


def _gather_corpus(rows: list[dict[str, Any]]) -> list[str]:
    """Union of every ground_truth_context across the dataset."""
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        for ctx in row.get("ground_truth_contexts") or []:
            ctx = (ctx or "").strip()
            if ctx and ctx not in seen:
                seen.add(ctx)
                out.append(ctx)
    return out


def _run_retrieval_only(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    # Import locally so a `--skip-ragas` run doesn't drag in ragas/langchain.
    from eval.runners.retrieval_runner import _evaluate as eval_retrieval

    return eval_retrieval(rows, k=k)


def _run_ragas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from eval.runners.ragas_runner import _evaluate as eval_ragas

    return eval_ragas(rows)


def _per_model(
    model: str,
    rows: list[dict[str, Any]],
    corpus: list[str],
    k: int,
    skip_ragas: bool,
) -> dict[str, Any]:
    logger.info("=" * 60)
    logger.info("Embedding model: %s", model)
    logger.info("=" * 60)

    coll_name = f"eval_{_slugify(model)}"
    retriever = ChromaRetriever(embed_model=model, collection_name=coll_name)

    t0 = time.time()
    n_indexed = retriever.rebuild_corpus(corpus)
    index_seconds = round(time.time() - t0, 1)
    logger.info("Indexed %d docs in %.1fs", n_indexed, index_seconds)

    set_active_retriever(retriever)
    try:
        t1 = time.time()
        retrieval_payload = _run_retrieval_only(rows, k=k)
        retrieval_payload["elapsed_seconds"] = round(time.time() - t1, 1)

        ragas_payload: dict[str, Any] | None = None
        if not skip_ragas:
            t2 = time.time()
            ragas_payload = _run_ragas(rows)
            ragas_payload["elapsed_seconds"] = round(time.time() - t2, 1)
    finally:
        set_active_retriever(None)

    return {
        "model": model,
        "n_indexed": n_indexed,
        "index_seconds": index_seconds,
        "retrieval": retrieval_payload,
        "ragas": ragas_payload,
    }


def _write_comparison_md(per_model: list[dict[str, Any]], path: Path, *, skip_ragas: bool) -> None:
    lines: list[str] = []
    lines.append("# Embedding-Model Comparison")
    lines.append("")
    lines.append(
        f"Generated: `{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}` · "
        "retrieval backend: ChromaDB (in-process) · "
        f"models: **{len(per_model)}**"
    )
    lines.append("")

    # Retrieval metrics
    lines.append("## Retrieval metrics (no LLM judge)")
    lines.append("")
    lines.append("| model | hit@1 | hit@3 | hit@5 | MRR | index s | eval s |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for entry in per_model:
        agg = entry["retrieval"]["aggregates"]
        lines.append(
            "| `{m}` | {h1:.3f} | {h3:.3f} | {h5:.3f} | {mrr:.3f} | {idx:.1f} | {ev:.1f} |".format(
                m=entry["model"],
                h1=agg["hit_at_1"],
                h3=agg["hit_at_3"],
                h5=agg["hit_at_5"],
                mrr=agg["mrr"],
                idx=entry["index_seconds"],
                ev=entry["retrieval"]["elapsed_seconds"],
            )
        )
    lines.append("")

    if not skip_ragas:
        lines.append("## RAGAS metrics (Groq judge)")
        lines.append("")
        lines.append(
            "| model | faithfulness | answer_relevancy | context_precision | context_recall | eval s |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|")
        for entry in per_model:
            r = entry.get("ragas") or {}
            agg = r.get("aggregates") or {}

            def fmt(k: str, agg=agg) -> str:  # bind agg at definition to avoid B023
                v = agg.get(k)
                return f"{v:.3f}" if isinstance(v, (int, float)) else "—"

            lines.append(
                "| `{m}` | {f} | {ar} | {cp} | {cr} | {ev:.1f} |".format(
                    m=entry["model"],
                    f=fmt("faithfulness"),
                    ar=fmt("answer_relevancy"),
                    cp=fmt("context_precision"),
                    cr=fmt("context_recall"),
                    ev=r.get("elapsed_seconds") or 0.0,
                )
            )
        lines.append("")

    lines.append("## What this is showing")
    lines.append("")
    lines.append(
        "Each row indexes the same eval corpus (union of every "
        "`ground_truth_contexts` paragraph in the dataset) into a fresh ChromaDB "
        "collection using a different sentence-transformers model, then runs the "
        "exact same eval rows against it. Higher numbers are better for every "
        "metric. **hit@k** = fraction of rows where retrieval surfaced a relevant "
        "chunk in the top-k. **MRR** = average `1 / rank_of_first_relevant_chunk`. "
        "**faithfulness** = answer claims grounded in retrieved context."
    )
    lines.append("")
    lines.append(
        "Generalist models often beat medical-specialist models on short-context "
        "clinical search (per arXiv 2401.01943) — if MiniLM or BGE-large beats "
        "PubMedBERT in your numbers, that's the published finding reproducing on "
        "your data, not an error. The *comparison itself* is the deliverable."
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--smoke", action="store_true", help="use the 5-row smoke set")
    parser.add_argument("--limit", type=int, default=None, help="first N rows only")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--skip-ragas", action="store_true", help="retrieval metrics only")
    parser.add_argument(
        "--models",
        default=None,
        help=f"comma-separated HF model ids (default: {','.join(DEFAULT_MODELS)})",
    )
    args = parser.parse_args()

    models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models
        else list(DEFAULT_MODELS)
    )

    dataset_path = settings.EVAL_SMOKE_DATASET_PATH if args.smoke else settings.EVAL_DATASET_PATH
    rows = load_dataset_rows(dataset_path, limit=args.limit)
    if not rows:
        raise SystemExit(
            f"No rows in {dataset_path}. Run `python -m eval.dataset.seed_pubmedqa` or pass --smoke."
        )

    corpus = _gather_corpus(rows)
    if not corpus:
        raise SystemExit(
            "Dataset rows have no ground_truth_contexts to index. "
            "Confirm the seed script populated them."
        )
    logger.info("Corpus size: %d unique contexts across %d rows", len(corpus), len(rows))

    overall_start = time.time()
    per_model: list[dict[str, Any]] = []
    for model in models:
        per_model.append(_per_model(model, rows, corpus, k=args.k, skip_ragas=args.skip_ragas))
    total_seconds = round(time.time() - overall_start, 1)

    # Save raw + comparison report
    results_dir = Path(settings.EVAL_RESULTS_DIR) / "embeddings"
    reports_dir = Path(settings.EVAL_REPORTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    raw_path = results_dir / f"compare_{timestamp}.json"
    raw_path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "n_rows": len(rows),
                "corpus_size": len(corpus),
                "total_seconds": total_seconds,
                "skip_ragas": args.skip_ragas,
                "per_model": per_model,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    md_path = reports_dir / "embedding_comparison.md"
    _write_comparison_md(per_model, md_path, skip_ragas=args.skip_ragas)

    logger.info("Done in %.1fs", total_seconds)
    logger.info("Raw:    %s", raw_path)
    logger.info("Report: %s", md_path)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
