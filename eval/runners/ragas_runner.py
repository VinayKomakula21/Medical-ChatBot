"""Run RAGAS metrics against the production retrieval + generation stack.

Free-tier only:
  - LLM judge: Groq (settings.RAGAS_LLM_MODEL, default llama-3.3-70b-versatile)
  - Embedding judge: local sentence-transformers (settings.RAGAS_EMBEDDING_MODEL)

Pipeline per row:
  1. Run production retrieval via app.db.pinecone.search_similar_documents.
     (Pure vector search; BM25 component of HybridSearchService requires a live
      in-memory index that's not populated outside the running server, so we
      evaluate the vector backbone here. Full hybrid eval is a follow-up plan.)
  2. Generate an answer by calling Groq with the same SYSTEM_PROMPT and
     user-content shape as production GroqChatService._generate_with_groq.
  3. Pass {question, retrieved_contexts, generated_answer, ground_truth} into
     RAGAS metrics: faithfulness, answer_relevancy, context_precision, context_recall.

Outputs:
  - eval/results/ragas_<timestamp>.json  (raw per-row + aggregates)
  - eval/reports/latest.md               (human-readable summary)

Usage:
  python -m eval.runners.ragas_runner                 # full dataset
  python -m eval.runners.ragas_runner --smoke         # 5-item smoke set
  python -m eval.runners.ragas_runner --limit 10      # first N rows
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from eval.runners._common import (
    aggregate_by_category,
    generate_answer_with_groq,
    load_dataset_rows,
    retrieve_contexts,
    set_active_retriever,
    write_markdown_report,
)
from eval.runners._retrievers import build_retriever

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _build_ragas_components():
    """Wire Groq as the LLM judge and local HF embeddings as the embedding judge.

    Imports are deferred so that the rest of the eval package stays importable
    even if RAGAS / langchain-groq aren't installed yet.
    """
    try:
        # langchain 0.3 split HuggingFaceEmbeddings into its own package.
        # Fall back to the deprecated langchain_community path for older envs.
        try:
            from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
        from langchain_groq import ChatGroq
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
    except ImportError as exc:
        raise SystemExit(
            "Missing eval deps. Install with: pip install -r requirements.txt "
            f"(missing: {exc.name})"
        ) from exc

    if not settings.GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY is not set. RAGAS judge needs it.")

    groq_llm = ChatGroq(
        model=settings.RAGAS_LLM_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0.0,
    )
    hf_emb = HuggingFaceEmbeddings(model_name=settings.RAGAS_EMBEDDING_MODEL)

    return LangchainLLMWrapper(groq_llm), LangchainEmbeddingsWrapper(hf_emb)


def _evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    ragas_llm, ragas_emb = _build_ragas_components()

    # Step 1+2: retrieve + generate for each row, building the RAGAS-shaped dataset.
    records: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        question = row["question"]
        ground_truth = row["ground_truth_answer"]
        ground_truth_contexts = row.get("ground_truth_contexts", [])
        category = row.get("category", "general")

        logger.info("[%d/%d] %s", i, len(rows), question[:80])

        retrieved_chunks = retrieve_contexts(question, k=5)
        retrieved_texts = [c["content"] for c in retrieved_chunks]

        answer = generate_answer_with_groq(
            question=question,
            retrieved_chunks=retrieved_chunks,
        )

        records.append(
            {
                "question": question,
                "answer": answer,
                "contexts": retrieved_texts or [""],
                "ground_truth": ground_truth,
                "reference_contexts": ground_truth_contexts,
                "category": category,
                "row_id": row.get("id", f"row-{i}"),
            }
        )

    # Step 3: RAGAS evaluation.
    ragas_dataset = Dataset.from_list(
        [
            {
                "question": r["question"],
                "answer": r["answer"],
                "contexts": r["contexts"],
                "ground_truth": r["ground_truth"],
            }
            for r in records
        ]
    )

    logger.info("Running RAGAS metrics (Groq judge — throttled by free-tier rate limit)…")
    result = evaluate(
        ragas_dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=ragas_llm,
        embeddings=ragas_emb,
        raise_exceptions=False,
    )

    df = result.to_pandas()
    metric_cols = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ]
    aggregates = {
        m: float(df[m].dropna().mean()) if m in df.columns else None
        for m in metric_cols
    }

    per_row: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        out = {
            "row_id": rec["row_id"],
            "question": rec["question"],
            "category": rec["category"],
            "answer": rec["answer"],
        }
        for m in metric_cols:
            if m in df.columns:
                val = df[m].iloc[i]
                out[m] = float(val) if val == val else None  # NaN -> None
        per_row.append(out)

    by_category = aggregate_by_category(per_row, metric_cols)

    return {
        "aggregates": aggregates,
        "by_category": by_category,
        "per_row": per_row,
        "thresholds": {
            "faithfulness": settings.EVAL_FAITHFULNESS_THRESHOLD,
            "context_precision": settings.EVAL_CONTEXT_PRECISION_THRESHOLD,
        },
        "judge_model": settings.RAGAS_LLM_MODEL,
        "embedding_model": settings.RAGAS_EMBEDDING_MODEL,
        "n_rows": len(records),
    }


def _save_results(payload: dict[str, Any]) -> tuple[Path, Path]:
    results_dir = Path(settings.EVAL_RESULTS_DIR)
    reports_dir = Path(settings.EVAL_REPORTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    json_path = results_dir / f"ragas_{timestamp}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_path = reports_dir / "latest.md"
    write_markdown_report(md_path, payload, kind="ragas", timestamp=timestamp)

    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--smoke", action="store_true", help="use the 5-item smoke set")
    parser.add_argument("--limit", type=int, default=None, help="first N rows only")
    parser.add_argument(
        "--retriever",
        choices=["pinecone", "chroma"],
        default="pinecone",
        help="which retrieval backend to use (default: pinecone — production path)",
    )
    parser.add_argument(
        "--embed-model",
        default=None,
        help="HF model id for sentence-transformers (chroma only)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="chroma collection name (default: slugified embed-model)",
    )
    args = parser.parse_args()

    # Activate retriever override before the runner kicks off retrieval.
    if args.retriever != "pinecone":
        retriever = build_retriever(
            args.retriever,
            embed_model=args.embed_model,
            collection_name=args.collection,
        )
        set_active_retriever(retriever)
        logger.info("Using retriever: %s (embed_model=%s)", retriever.name, args.embed_model)

    dataset_path = (
        settings.EVAL_SMOKE_DATASET_PATH if args.smoke else settings.EVAL_DATASET_PATH
    )
    rows = load_dataset_rows(dataset_path, limit=args.limit)
    if not rows:
        raise SystemExit(
            f"No rows loaded from {dataset_path}. "
            "Run `python -m eval.dataset.seed_pubmedqa` first, or pass --smoke."
        )

    start = time.time()
    payload = _evaluate(rows)
    elapsed = time.time() - start
    payload["elapsed_seconds"] = round(elapsed, 1)
    payload["retriever"] = args.retriever
    if args.retriever == "chroma":
        payload["retriever_embed_model"] = args.embed_model

    json_path, md_path = _save_results(payload)

    logger.info("Done in %.1fs", elapsed)
    logger.info("Aggregates: %s", payload["aggregates"])
    logger.info("Results: %s", json_path)
    logger.info("Report:   %s", md_path)


if __name__ == "__main__":
    # Make `python -m eval.runners.ragas_runner` work even if cwd is something odd.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
