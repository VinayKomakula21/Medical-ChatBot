# Medical-ChatBot — AI Engineer Portfolio Improvement Plan

A 2026-calibrated roadmap to upgrade this project from a "competent RAG chatbot" into a **portfolio piece that signals senior-AI-Engineer-readiness** at hiring time.

---

## 1. Why this plan exists

This project today is a solid full-stack RAG chatbot: FastAPI + React 19, hybrid retrieval (vector + BM25 with Reciprocal Rank Fusion), Pinecone, Groq Llama-3.1-8B, Google OAuth, SQLAlchemy.

What it is missing — and what the 2026 AI Engineer job market expects — is **evaluation rigor, production observability, agentic behavior, and honest measurement of trade-offs**. The 2026 hiring consensus across multiple sources: *"Most AI engineers ship without evaluation; the ones who get hired know how to write tests for non-deterministic systems."*

This plan closes that gap.

---

## 2. Current State Snapshot

| Area | Status | Score |
|------|--------|-------|
| RAG architecture (hybrid + query decomposition) | Solid | 8/10 |
| Full-stack engineering (FastAPI async + React 19 + TS strict) | Solid | 8/10 |
| Vector store + embeddings pipeline | Working | 7/10 |
| Auth (Google OAuth + JWT) | Working | 8/10 |
| **Evaluation / RAGAS / metrics** | **None** | **0/10** |
| **Observability / tracing / cost tracking** | **None** | **2/10** |
| **Tests (unit + integration)** | **None** | **0/10** |
| **CI/CD (GitHub Actions)** | **None** | **0/10** |
| **Docker / reproducible deploys** | **None** | **0/10** |
| Streaming | Faked via time.sleep chunking | 3/10 |
| Agentic behavior / tool use | None — pure single-turn RAG | 0/10 |
| Multi-modal support | None | 0/10 |
| Documentation | Good README + PORTFOLIO.md | 7/10 |

---

## 3. 2026 Trend-Backed Tech Choices

Each upgrade below is justified by current (2026) industry trends and benchmark data. Sources are listed at the bottom.

### 3.1 Evaluation — RAGAS + DeepEval combo
- **RAGAS** for the four core RAG metrics: faithfulness, answer relevance, context precision, context recall.
- **DeepEval** for `pytest` integration → evals run in GitHub Actions on every PR.
- **Seed dataset**: 50 Q&A pairs curated from **PubMedQA** + **MedQA** (open HuggingFace datasets) with ground-truth contexts.
- Why both: 2026 industrial pattern is to combine — RAGAS is RAG-specific and quick; DeepEval gives CI/CD muscle.

### 3.2 Observability — Langfuse (not LangSmith)
- Your Groq calls are raw HTTP, not LangChain. LangSmith shines for LangChain users; **Langfuse is the framework-agnostic 2026 choice**.
- Acquired by **ClickHouse in Jan 2026** → stable bet.
- Free hobby tier: 50k events/month, no per-seat fee.
- Add **Arize Phoenix** locally for embedding-drift visualization screenshots (one extra screenshot in PORTFOLIO.md = strong signal).

### 3.3 Reranker — Jina Reranker v3 (not plain BGE-Reranker v2)
2026 reranker leaderboard (top of the leaderboard, not 2024's picks):

| Reranker | Latency | Quality | Notes |
|---|---|---|---|
| **Jina Reranker v3** ⭐ | ~188ms | SOTA BEIR (61.94 nDCG@10) | Fast + free tier — recommended |
| Cohere Rerank v4.0 Pro | ~600ms | 1629 ELO | Production-trusted API alternative |
| bge-reranker-v2-m3 | ~300ms GPU | Top open-source | Pick if you want to self-host |
| Nemotron-rerank-1b | ~243ms | Highest accuracy (83% Hit@1) | NVIDIA-backed; resume keyword |
| BGE-Reranker v2 (older) | — | Beaten by v2-m3 + v3 | Skip — outdated for 2026 |

**Action**: ship Jina v3, but publish a 3-way comparison (hybrid-only / hybrid+Jina / hybrid+Cohere). The *comparison* is what impresses, not the choice.

### 3.4 Streaming — True Groq SSE
- Groq supports OpenAI-compatible SSE streaming natively.
- Replace the current fake-chunking-with-`time.sleep` with real `EventSource` (SSE) or clean up the existing WebSocket.

### 3.5 Hallucination detection — claim-level, not entity-level
The "verify entity in source" approach is too brittle (fails on paraphrase). The 2026 state-of-the-art for medical:
- **Claim-level faithfulness scoring** — RAGAS already gives this; reuse it at runtime as a guard.
- **MEGA-RAG-style multi-evidence verification** — require ≥2 retrieved chunks supporting a claim. Published 40% hallucination reduction in public-health domain.
- **Medical guardrails layer**: scope refusal ("I cannot diagnose"), emergency keyword routing (you already have this — surface it), PII scrubbing, drug-name validation against RxNorm.

### 3.6 Agentic RAG — LangGraph + Groq native tool use
- **Framework: LangGraph** — passed CrewAI in stars early 2026; fastest latency in a 2,000-task independent benchmark; checkpointing + node-level retries are what hiring managers ask about.
- **LLM: Groq `llama-3.3-70b-versatile` or `llama-3-groq-70b-tool-use`** via OpenAI-compatible function-calling API. No LangChain wrapper needed.
- **Tools (all free, no licensing hassles)**:
  - `search_pubmed` — NCBI E-utilities (free, no key)
  - `lookup_drug_openfda` — OpenFDA (free, no auth: drug labels, recalls, adverse events)
  - `check_interaction_rxnorm` — NIH RxNorm (free)
  - `search_internal_kb` — your existing hybrid RAG, wrapped as a tool
- **Bonus**: expose these as an **MCP server**. Groq supports MCP natively; "MCP" is a 2026 resume keyword.

### 3.7 Embedding model comparison (high ROI, surprising result)
Important 2026 research finding: **PubMedBERT / BioBERT / MedCPT don't always beat generalist models (E5, BGE) on short-context clinical search.** State-of-the-art `MedTE` (avg 0.578) edges out competitors but isn't production-ready.

Practical play: run your eval with **three** embedding models and publish the comparison —
1. `sentence-transformers/all-MiniLM-L6-v2` (current baseline)
2. `NeuML/pubmedbert-base-embeddings` (medical specialist)
3. `BAAI/bge-large-en-v1.5` (general SOTA)

A *negative result* ("specialist didn't beat generalist on my eval set — here's why") is **more interesting in an interview** than "I picked the medical one because medical."

### 3.8 Python tooling modernization
- Replace `requirements.txt` + `pip` with **`uv`** (Astral's Rust-based package manager — the 2026 standard).
- Add `pyproject.toml` with **ruff + mypy** configs.
- Replace `requests` (sync) with `httpx.AsyncClient` inside async services.
- Add **pre-commit hooks**.

### 3.9 Production hygiene
- **Dockerfile** + `docker-compose.yml` (Postgres + app for local).
- **GitHub Actions CI**: ruff, mypy, pytest, frontend `tsc --noEmit` + ESLint, eval suite with score-threshold gate.
- **Cost/latency table** in README (per-1000-query breakdown: Groq + Jina + Pinecone + HF) + p50/p95 latency.
- **Eval badge in README**: "RAG faithfulness: 0.87".

---

## 4. Consolidated Execution Order

| # | Item | Hours | Priority |
|---|---|---|---|
| 1 | RAGAS + DeepEval eval suite + PubMedQA seed dataset | 5–6 | Must |
| 2 | Langfuse tracing on Groq calls | 1–2 | Must |
| 3 | Embedding model 3-way comparison, publish results | 3–4 | Must |
| 4 | Jina v3 reranker + comparison eval | 2 | Must |
| 5 | True Groq SSE streaming (kill the fake chunking) | 2–3 | High |
| 6 | SafetyService — RAGAS-based runtime faithfulness check | 3–4 | High |
| 7 | `uv` + `pyproject.toml` + ruff + mypy + `httpx` async | 2 | High |
| 8 | Dockerfile + GitHub Actions CI with eval-score gate | 3 | High |
| 9 | LangGraph agent with PubMed + OpenFDA + RxNorm + KB tools | 10–14 | 10x |
| 10 | Architecture diagram + cost/latency table + Phoenix screenshots in README/PORTFOLIO.md | 3 | Polish |

**Total**: ~35–45 hours. ~2 focused weeks of evenings.

---

## 5. The Resume Bullet This Earns You

> "Built production-style agentic medical RAG with LangGraph (Groq native tool-use over PubMed / OpenFDA / RxNorm). Established RAGAS + DeepEval pipeline gating CI; improved retrieval precision@5 by Xx% via Jina-v3 reranker (measured against curated PubMedQA test set). Layered runtime hallucination detection (claim-level faithfulness, MEGA-RAG-style multi-evidence verification). Full Langfuse observability with cost/latency dashboards."

— with an actual repo, actual eval numbers, and actual screenshots to back every claim.

---

## 6. Sources (2026 research)

**Evaluation frameworks**
- [RAGAS, TruLens, DeepEval: LLM Evaluation Frameworks (2026) — Atlan](https://atlan.com/know/llm-evaluation-frameworks-compared/)
- [Top 5 RAG Evaluation Tools 2026 — Maxim](https://www.getmaxim.ai/articles/the-5-best-rag-evaluation-tools-you-should-know-in-2026/)
- [LLM Evaluation Tools Comparison — Inference.net](https://inference.net/content/llm-evaluation-tools-comparison/)

**Observability**
- [Best LLM Observability Tools 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-llm-observability-tools)
- [Agent Observability: LangSmith, Langfuse, Arize 2026 — DigitalApplied](https://www.digitalapplied.com/blog/agent-observability-platforms-langsmith-langfuse-arize-2026)
- [Langfuse alternatives 2026 — Laminar](https://laminar.sh/article/langfuse-alternatives-2026)

**Rerankers**
- [Best Rerankers Leaderboard — Agentset](https://agentset.ai/rerankers)
- [Top 8 Rerankers: Quality vs Cost — Medium](https://medium.com/@bhagyarana80/top-8-rerankers-quality-vs-cost-4e9e63b73de8)
- [jina-reranker-v3 — Jina AI](https://jina.ai/models/jina-reranker-v3/)
- [Ultimate Guide to Reranking Models — ZeroEntropy](https://zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025/)

**Medical hallucination & safety**
- [CuraView: Multi-Agent Medical Hallucination Detection — arXiv](https://arxiv.org/html/2605.03476)
- [Clinical safety and hallucination rates of LLMs for medical summarisation — Nature npj Digital Medicine](https://www.nature.com/articles/s41746-025-01670-7)
- [MEGA-RAG: multi-evidence guided answer refinement — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12540348/)

**Agentic frameworks**
- [10 AI Agent Frameworks You Should Know in 2026 — Medium](https://medium.com/@atnoforgenai/10-ai-agent-frameworks-you-should-know-in-2026-langgraph-crewai-autogen-more-2e0be4055556)
- [LangGraph vs CrewAI vs AutoGen 2026 — Data Science Collective](https://medium.com/data-science-collective/langgraph-vs-crewai-vs-autogen-which-agent-framework-should-you-actually-use-in-2026-b8b2c84f1229)
- [Agent framework production comparison — BSWEN](https://docs.bswen.com/blog/2026-04-29-agent-framework-production-comparison/)

**Medical embeddings**
- [NeuML/pubmedbert-base-embeddings — Hugging Face](https://huggingface.co/NeuML/pubmedbert-base-embeddings)
- [Generalist embeddings outperform specialist on short-context clinical search — arXiv](https://arxiv.org/html/2401.01943v2)
- [Towards Domain Specification of Embedding Models in Medicine (MedTE) — arXiv](https://arxiv.org/html/2507.19407v1)
- [MedCPT — arXiv](https://arxiv.org/pdf/2307.00589)

**AI Engineer hiring 2026**
- [Best GenAI Portfolio Projects 2026 — IdolsRM](https://idolsrm.in/ai-portfolio-projects-2026/)
- [5 AI Portfolio Projects That Get You Hired in 2026 — DEV](https://dev.to/klement_gunndu/5-ai-portfolio-projects-that-actually-get-you-hired-in-2026-5bpl)
- [How to Hire RAG Engineers in 2026 — Kore1](https://www.kore1.com/hire-rag-engineers-2026/)
- [AI Engineer Roadmap 2026: 5 Production Projects — The AI Corner](https://www.the-ai-corner.com/p/ai-engineer-roadmap-production-projects-2026)

**Groq tool use**
- [Tool Use Overview — Groq Docs](https://console.groq.com/docs/tool-use/overview)
- [Llama-3-Groq-Tool-Use Models — Groq Blog](https://groq.com/blog/introducing-llama-3-groq-tool-use-models)
