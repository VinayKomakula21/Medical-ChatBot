"""Retrieval-only eval: hit@k and MRR. No LLM judge needed.

Cheap (no API calls beyond Pinecone search + HF embeddings already in use) and
fast enough to run on every change while tuning retrieval. Designed to be the
"inner loop" tool — use ragas_runner for the slower, deeper quality signal.

Matching: a retrieved chunk "hits" a ground-truth context if the normalized
fuzzy-match ratio (rapidfuzz.token_set_ratio) ≥ MATCH_THRESHOLD. This handles
the common case where retrieval returns an overlapping chunk of the source
abstract, not the exact paragraph.

Usage:
  python -m eval.runners.retrieval_runner
  python -m eval.runners.retrieval_runner --smoke
  python -m eval.runners.retrieval_runner --limit 20 --k 10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.core.config import settings
from eval.runners._common import (
    aggregate_by_category,
    load_dataset_rows,
    retrieve_contexts,
    set_active_retriever,
    write_markdown_report,
)
from eval.runners._retrievers import build_retriever

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 85  # rapidfuzz token_set_ratio ≥ 85 ⇒ chunk overlaps gt context


def _is_match(retrieved: str, gt_contexts: list[str]) -> bool:
    try:
        from rapidfuzz import fuzz
    except ImportError as exc:
        raise SystemExit(
            "rapidfuzz missing. Install with: pip install -r requirements.txt"
        ) from exc

    r = (retrieved or "").strip()
    if not r:
        return False
    for gt in gt_contexts:
        gt_str = (gt or "").strip()
        if not gt_str:
            continue
        # token_set_ratio is robust to length differences (chunked retrieved vs
        # full abstract ground truth) and to punctuation differences.
        if fuzz.token_set_ratio(r, gt_str) >= MATCH_THRESHOLD:
            return True
    return False


def _score_row(question: str, gt_contexts: list[str], k: int) -> dict[str, Any]:
    retrieved = retrieve_contexts(question, k=k)
    if not retrieved:
        return {
            "hit_at_1": 0,
            "hit_at_3": 0,
            "hit_at_5": 0,
            "mrr": 0.0,
            "retrieved_count": 0,
        }

    hits = [_is_match(r.get("content", ""), gt_contexts) for r in retrieved]

    reciprocal_rank = 0.0
    for rank, hit in enumerate(hits, start=1):
        if hit:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "hit_at_1": int(any(hits[:1])),
        "hit_at_3": int(any(hits[:3])),
        "hit_at_5": int(any(hits[:5])),
        "mrr": reciprocal_rank,
        "retrieved_count": len(retrieved),
    }


def _evaluate(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    metric_cols = ["hit_at_1", "hit_at_3", "hit_at_5", "mrr"]
    per_row: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        question = row["question"]
        gt = row.get("ground_truth_contexts", [])
        category = row.get("category", "general")
        logger.info("[%d/%d] %s", i, len(rows), question[:80])

        scores = _score_row(question, gt, k=k)
        per_row.append(
            {
                "row_id": row.get("id", f"row-{i}"),
                "question": question,
                "category": category,
                **scores,
            }
        )

    aggregates = {m: round(mean(r[m] for r in per_row), 4) for m in metric_cols}
    by_category = aggregate_by_category(per_row, metric_cols)

    return {
        "aggregates": aggregates,
        "by_category": by_category,
        "per_row": per_row,
        "thresholds": {"hit_at_5": settings.EVAL_HIT_AT_5_THRESHOLD},
        "match_threshold": MATCH_THRESHOLD,
        "k": k,
        "n_rows": len(per_row),
    }


def _save_results(payload: dict[str, Any]) -> tuple[Path, Path]:
    results_dir = Path(settings.EVAL_RESULTS_DIR)
    reports_dir = Path(settings.EVAL_REPORTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    json_path = results_dir / f"retrieval_{timestamp}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_path = reports_dir / "latest.md"
    write_markdown_report(md_path, payload, kind="retrieval", timestamp=timestamp)

    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--k", type=int, default=5, help="top-k for retrieval")
    parser.add_argument(
        "--retriever",
        choices=["pinecone", "chroma"],
        default="pinecone",
    )
    parser.add_argument("--embed-model", default=None)
    parser.add_argument("--collection", default=None)
    args = parser.parse_args()

    if args.retriever != "pinecone":
        retriever = build_retriever(
            args.retriever,
            embed_model=args.embed_model,
            collection_name=args.collection,
        )
        set_active_retriever(retriever)
        logger.info("Using retriever: %s (embed_model=%s)", retriever.name, args.embed_model)

    dataset_path = settings.EVAL_SMOKE_DATASET_PATH if args.smoke else settings.EVAL_DATASET_PATH
    rows = load_dataset_rows(dataset_path, limit=args.limit)
    if not rows:
        raise SystemExit(
            f"No rows loaded from {dataset_path}. "
            "Run `python -m eval.dataset.seed_pubmedqa` first, or pass --smoke."
        )

    start = time.time()
    payload = _evaluate(rows, k=args.k)
    payload["elapsed_seconds"] = round(time.time() - start, 1)
    payload["retriever"] = args.retriever
    if args.retriever == "chroma":
        payload["retriever_embed_model"] = args.embed_model

    json_path, md_path = _save_results(payload)

    logger.info("Done in %.1fs", payload["elapsed_seconds"])
    logger.info("Aggregates: %s", payload["aggregates"])
    logger.info("Results: %s", json_path)
    logger.info("Report:   %s", md_path)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
