"""PubMed search tool — NCBI E-utilities (free).

esearch → list of PMIDs for a query.
esummary → titles + abstracts for those PMIDs.

Rate limits (free): 3 req/sec without key, 10 req/sec with NCBI_API_KEY.
"""

from __future__ import annotations

import logging

import httpx
from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_TIMEOUT = 8.0


@tool
def search_pubmed(query: str, max_results: int = 5) -> str:
    """Search PubMed for medical research papers matching a query.

    Use this when the user asks about clinical evidence, recent research,
    or wants citations to peer-reviewed literature. Returns titles and
    one-line summaries of the top matching papers.

    Args:
        query: a medical search query (e.g. "metformin cardiovascular outcomes")
        max_results: how many results to return (max 10).

    Returns:
        A bulleted string of matching papers, or an error/empty message.
    """
    max_results = max(1, min(int(max_results or 5), 10))
    params: dict = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(max_results),
    }
    if settings.NCBI_API_KEY:
        params["api_key"] = settings.NCBI_API_KEY

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            search = client.get(f"{_EUTILS}/esearch.fcgi", params=params)
            if search.status_code != 200:
                return f"PubMed esearch error: HTTP {search.status_code}"
            ids: list[str] = search.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return f"No PubMed results for: {query}"

            summary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
            if settings.NCBI_API_KEY:
                summary_params["api_key"] = settings.NCBI_API_KEY
            summary = client.get(f"{_EUTILS}/esummary.fcgi", params=summary_params)
            if summary.status_code != 200:
                return f"PubMed esummary error: HTTP {summary.status_code}"
    except httpx.HTTPError as exc:
        logger.warning("PubMed transport error: %s", exc)
        return f"PubMed transport error: {exc}"

    result = summary.json().get("result", {})
    lines: list[str] = []
    for pmid in ids:
        item = result.get(pmid) or {}
        title = item.get("title", "(no title)")
        journal = item.get("source", "")
        year = item.get("pubdate", "")[:4]
        lines.append(f"- [{pmid}] {title} — {journal} ({year})")
    return "\n".join(lines)
