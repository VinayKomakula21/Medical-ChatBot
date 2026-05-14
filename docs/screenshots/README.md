# Screenshots — capture checklist

Add the following PNGs (or one looping MP4/GIF) to this directory and link them from the top-level `README.md`. Aim for a recruiter-quality demo: every shot should clearly show one differentiator.

1. **`chat_streaming.png`** — chat UI mid-response, with Groq SSE tokens visibly streaming, plus the source-citation badge below the assistant bubble. Capture in dark mode for contrast.
2. **`source_citations.png`** — a completed answer that visibly cites `[1]` / `[2]` markers tied to source pills (filename + relevance score). Demonstrates grounded retrieval.
3. **`langfuse_trace.png`** — Langfuse trace tree for a single chat request showing the `retrieval → hybrid_search → rerank.jina → groq.chat_completion → safety.*` span hierarchy. Demonstrates observability.
4. **`agent_tool_calls.png`** — agent endpoint response (or Langfuse trace) showing the LangGraph agent calling `search_pubmed` + `lookup_drug_openfda` for one prompt, with `tool_calls` array visible. Demonstrates agentic RAG.
5. *(optional)* **`demo.gif`** — 10–20s loop covering: upload a PDF → ask a question → stream answer with citations. Keep under 5 MB.

After capturing, edit the parent `README.md` "Screenshots" section to inline-embed the most impactful image:

```md
![Chat streaming with source citations](docs/screenshots/chat_streaming.png)
```

GitHub renders relative paths directly, so no CDN required.
