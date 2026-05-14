"""Build the medical RAG eval dataset from PubMedQA.

PubMedQA (qiaojin/PubMedQA, "pqa_labeled" subset) is a 1k-item open dataset of
biomedical research questions with human-labeled yes/no/maybe answers, each
backed by a PubMed abstract. Free to use, no auth required.

This script is one-shot: it samples N items, normalizes them into the eval row
schema, and writes JSONL. Re-run any time to refresh / expand the dataset.

Usage:
    python -m eval.dataset.seed_pubmedqa --n 50 --out eval/dataset/medical_qa_eval.jsonl

After running, you must also upload the source abstracts to Pinecone (via the
existing /api/v1/documents upload endpoint) so retrieval has something to find.
See eval/README.md for the full setup walkthrough.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path
from typing import Iterable

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _classify(question: str, long_answer: str) -> str:
    """Coarse category mirroring query_processor.classify_query_type."""
    q = question.lower()
    a = long_answer.lower()
    if any(k in q for k in ("symptom", "sign of", "presents with")):
        return "symptom"
    if any(k in q for k in ("treat", "therapy", "manage", "drug", "medication")):
        return "treatment"
    if any(k in q for k in ("diagnos", "detect", "test for", "screen")):
        return "diagnosis"
    if any(k in q for k in ("prevent", "reduce risk", "avoid")):
        return "prevention"
    if "treat" in a or "therapy" in a:
        return "treatment"
    return "general"


def _to_row(idx: int, item: dict) -> dict:
    contexts = item.get("context", {}).get("contexts") or []
    long_answer = item.get("long_answer", "") or ""
    question = item.get("question", "") or ""
    final_decision = item.get("final_decision", "") or ""
    answer = (
        f"{final_decision.capitalize()}. {long_answer}".strip(". ").strip()
        if final_decision
        else long_answer
    )
    return {
        "id": f"pubmedqa-{idx:04d}",
        "question": question,
        "ground_truth_answer": answer,
        "ground_truth_contexts": contexts,
        "category": _classify(question, long_answer),
        "source": "pubmedqa",
    }


def _iter_pubmedqa(n: int, seed: int) -> Iterable[dict]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "datasets package missing. Install with: pip install datasets"
        ) from exc

    logger.info("Loading PubMedQA (pqa_labeled, ~1k items)…")
    ds = load_dataset("qiaojin/PubMedQA", "pqa_labeled", split="train")
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)

    yielded = 0
    for idx in indices:
        if yielded >= n:
            break
        item = ds[idx]
        if not item.get("question") or not item.get("long_answer"):
            continue
        if not item.get("context", {}).get("contexts"):
            continue
        yield _to_row(yielded + 1, item)
        yielded += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--n", type=int, default=50, help="number of rows to sample")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("eval/dataset/medical_qa_eval.jsonl"),
        help="output JSONL path",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w", encoding="utf-8") as f:
        for row in _iter_pubmedqa(args.n, args.seed):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info("Wrote %s", args.out)
    logger.info(
        "Next: upload the source abstracts to Pinecone via /api/v1/documents/upload "
        "so retrieval has something to find. See eval/README.md."
    )


if __name__ == "__main__":
    main()
