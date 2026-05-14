"""Internal KB tool — exposes the existing hybrid RAG as an agent tool.

The agent uses this when the user's question is about their *uploaded*
medical documents rather than general literature (PubMed) or specific drug
labels (OpenFDA). It's the same search HybridSearchService runs in the
non-agentic chat path — including the reranker if one is configured.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from app.services.hybrid_search import hybrid_search_service

logger = logging.getLogger(__name__)


@tool
def search_internal_kb(query: str, top_k: int = 5) -> str:
    """Search the user's uploaded medical documents (their personal knowledge base).

    Use this for questions like "what did my uploaded guideline say about X" or
    when the user asks something likely to be answered by their own documents.

    Args:
        query: search query.
        top_k: how many top chunks to return (1-10).

    Returns:
        Bulleted top-k chunks with citation refs, or a "no results" message.
    """
    top_k = max(1, min(int(top_k or 5), 10))
    results = hybrid_search_service.search(query=query, top_k=top_k)
    if not results:
        return f"No matches in the user's uploaded documents for: {query}"

    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        filename = (r.get("metadata") or {}).get("filename", "doc")
        content = (r.get("content") or "")[:300].replace("\n", " ").strip()
        lines.append(f"[{i}] ({filename}) {content}")
    return "\n".join(lines)
