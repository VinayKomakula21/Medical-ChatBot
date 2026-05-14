# Evaluation Suite

This directory contains the offline evaluation infrastructure for the Medical-ChatBot's RAG pipeline. **Everything here runs on the free tier** — no paid API keys required beyond what the app already uses (Groq + Pinecone + HuggingFace, all free).

## What this measures

| Metric | What it answers | Where it comes from |
|---|---|---|
| **hit@k** (k=1,3,5) | Did retrieval return a relevant chunk in the top-k? | retrieval_runner |
| **MRR** (Mean Reciprocal Rank) | How high up does the first relevant chunk appear? | retrieval_runner |
| **faithfulness** | Does the answer only state things the retrieved chunks support? (catches hallucinations) | RAGAS |
| **answer_relevancy** | Does the answer actually address the question? | RAGAS |
| **context_precision** | Of the chunks we retrieved, how many were actually relevant? | RAGAS |
| **context_recall** | Of the chunks we *should* have retrieved, how many did we? | RAGAS |

## How RAGAS works without OpenAI

RAGAS uses an LLM as a judge to score answers. We route this through **Groq** (free tier: 30 req/min, 14,400 req/day) instead of OpenAI. The judge model defaults to `llama-3.3-70b-versatile` — intentionally larger than the production LLM (`llama-3.1-8b-instant`) so it can fairly grade the smaller model's output. Embeddings use local `sentence-transformers` (also free, already in the project).

A 50-row full RAGAS run takes ~10–15 minutes wall-clock because of the Groq free-tier rate limit. The retrieval-only runner is much faster (no LLM calls).

## One-time setup

1. **Install eval deps** (already in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```

2. **Seed the dataset** from PubMedQA:
   ```bash
   python -m eval.dataset.seed_pubmedqa --n 50
   ```
   Produces `eval/dataset/medical_qa_eval.jsonl` (50 rows by default).

3. **Upload the source abstracts to Pinecone** so retrieval has something to find. The eval rows contain `ground_truth_contexts` — those need to be in your vector index. Options:
   - Easiest: paste the abstracts into a `.txt` file and upload via the existing `POST /api/v1/documents/upload` endpoint.
   - Or extend `seed_pubmedqa.py` to write the contexts to a `.txt` file you upload through the UI.

4. **Confirm env vars are set** (in `.env`):
   - `GROQ_API_KEY` — for both production and the RAGAS judge.
   - `PINECONE_API_KEY` — for retrieval.
   - `HF_TOKEN` — for production embeddings (not used by eval directly; the local sentence-transformers path is used for RAGAS).

## Running the evals

```bash
# Fast: retrieval-only, runs against the 50-row set
python -m eval.runners.retrieval_runner

# Full quality eval (slower, ~10-15 min on free tier)
python -m eval.runners.ragas_runner

# Quick smoke tests against the 5 hand-crafted items
python -m eval.runners.retrieval_runner --smoke
python -m eval.runners.ragas_runner --smoke

# First N rows only
python -m eval.runners.ragas_runner --limit 10

# Point a single run at a non-production retriever (Item #3)
python -m eval.runners.retrieval_runner \
    --retriever chroma \
    --embed-model BAAI/bge-large-en-v1.5
```

## Embedding-model 3-way comparison (Item #3)

The eval harness can compare different embedding models against the same
dataset without touching production Pinecone:

```bash
# Compare all three default models (MiniLM / PubMedBERT / BGE-large)
python -m eval.runners.embedding_compare

# Smoke run (5 rows, retrieval metrics only — < 1 min after first model download)
python -m eval.runners.embedding_compare --smoke --skip-ragas

# Custom model list
python -m eval.runners.embedding_compare \
    --models sentence-transformers/all-MiniLM-L6-v2,BAAI/bge-base-en-v1.5
```

How it works:
1. Reads the eval dataset and unions every `ground_truth_contexts` paragraph
   into a single corpus.
2. For each embedding model in the list, builds a fresh ChromaDB collection,
   indexes the corpus locally with `sentence-transformers` (no API calls).
3. Points the existing eval runners at that collection via an in-memory
   retriever override — production Pinecone path is untouched.
4. Writes `eval/results/embeddings/compare_<timestamp>.json` (raw) and
   `eval/reports/embedding_comparison.md` (table).

Disk + time cost (all free):
- First-time download of HF models: ~2 GB combined into `~/.cache/huggingface/`
  (MiniLM ~90 MB, PubMedBERT ~440 MB, BGE-large ~1.3 GB). Subsequent runs are
  cached.
- ChromaDB collections persist under `eval/.chroma/` so re-runs of the same
  model are nearly instant. Delete that directory to force a clean rebuild.
- Wall-clock: smoke + skip-ragas finishes in ~2 min (model loads dominate);
  full dataset with RAGAS is ~30 min total (rate-limited by Groq free tier).

Outputs:
- `eval/results/<runner>_<timestamp>.json` — full raw scores (gitignored).
- `eval/reports/latest.md` — human-readable summary (always reflects last run).

## Running the gated tests (CI-ready)

```bash
# Slow tests are excluded by default. Run them explicitly:
pytest -m slow tests/eval/
```

Each test runs the relevant runner against the 5-item smoke set and asserts the aggregate score stays above the threshold configured in `app/core/config.py`:

- `EVAL_HIT_AT_5_THRESHOLD` (default 0.60)
- `EVAL_FAITHFULNESS_THRESHOLD` (default 0.75)
- `EVAL_CONTEXT_PRECISION_THRESHOLD` (default 0.70)

If a future change (reranker swap, embedding swap, prompt edit) drops a metric below its threshold, the test fails loudly with the actual number. Wire this into GitHub Actions later to gate merges.

## Metric definitions (quick reference)

**Faithfulness** (0–1, higher = better): every claim in the answer can be inferred from the retrieved context. Score 1.0 means no claim is unsupported. Sub-1.0 means at least one claim has no grounding (a hallucination signal).

**Answer relevancy** (0–1, higher = better): does the answer address the question? Measured by generating questions from the answer and comparing them to the original via embedding similarity.

**Context precision** (0–1, higher = better): of the chunks the retriever returned, what fraction are actually relevant? Low precision = retrieval is bringing back noise.

**Context recall** (0–1, higher = better): of the ground-truth contexts, what fraction did the retriever find? Low recall = retrieval is missing important sources.

**hit@k**: binary per row — was at least one relevant chunk in the top-k? Aggregate = fraction of rows that "hit".

**MRR**: averaged `1 / rank_of_first_relevant_chunk`. Higher = relevant chunks appear earlier in results.

## Extending the dataset

The seed script samples PubMedQA. To add more / different questions:

1. Edit `seed_pubmedqa.py` or write a new seeder.
2. Or hand-write rows into `medical_qa_eval.jsonl` matching the schema:
   ```json
   {
     "id": "custom-001",
     "question": "...",
     "ground_truth_answer": "...",
     "ground_truth_contexts": ["..."],
     "category": "symptom|treatment|diagnosis|prevention|general",
     "source": "hand-written"
   }
   ```

The smoke set (`medical_qa_eval_smoke.jsonl`) is 5 hand-crafted items used by the pytest gates — keep it small and stable so CI runs fast.

## Cost

Zero dollars. Everything routes through:
- Groq free tier (30 req/min)
- Local sentence-transformers (no API)
- Pinecone free tier (1 index, 100k vectors)

Time, not money, is the bottleneck — RAGAS on 50 rows ≈ 10–15 min; retrieval-only on 50 rows ≈ <30s.

## What this unlocks

Now that there's a measurement harness, the next upgrades have numbers to point at:

- **Reranker swap** (Jina v3): rerun both runners, publish before/after.
- **Embedding swap** (PubMedBERT vs BGE-large): same.
- **Prompt edits**: rerun RAGAS, watch faithfulness.
- **Agentic upgrade** (LangGraph + PubMed/OpenFDA/RxNorm tools): the agent's output is evaluated against the *same* dataset — apples-to-apples vs the current RAG.

See `../IMPROVEMENT_PLAN.md` for the broader roadmap.
