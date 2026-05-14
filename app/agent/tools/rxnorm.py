"""Drug-drug interaction tool — wraps app.clients.rxnorm (free NIH).

The agent calls this when the user asks about combining medications. Reuses
the same RxNormClient that the SafetyService uses (Item #6).
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.tools import tool

from app.clients.rxnorm import rxnorm_client

logger = logging.getLogger(__name__)


@tool
def check_drug_interactions(drug_names: list[str]) -> str:
    """Check NIH RxNorm for known interactions between a list of drugs.

    Use this when the user asks whether two or more medications can be taken
    together, or about combining a new prescription with their existing meds.

    Args:
        drug_names: 2+ drug names (brand or generic).

    Returns:
        Structured list of interactions with severity, or a no-interactions
        message. Free NIH source — not exhaustive; major interactions tend
        to be well-covered.
    """
    if not drug_names or len(drug_names) < 2:
        return "Please provide at least two drug names to check for interactions."

    async def _run() -> str:
        # 1. Resolve each name to its RXCUI concept id.
        rxcui_tasks = [rxnorm_client.find_rxcui(n) for n in drug_names]
        rxcuis_or_none = await asyncio.gather(*rxcui_tasks)
        resolved = [
            (name, rxcui) for name, rxcui in zip(drug_names, rxcuis_or_none, strict=True) if rxcui
        ]
        if len(resolved) < 2:
            unresolved = [n for n, r in zip(drug_names, rxcuis_or_none, strict=True) if not r]
            return f"Could not resolve in RxNorm: {', '.join(unresolved)}"

        rxcuis = [r for _, r in resolved]
        interactions = await rxnorm_client.list_interactions(rxcuis)
        if not interactions:
            return (
                f"No known interactions in NIH RxNorm between: {', '.join(n for n, _ in resolved)}."
            )

        out = ["**Known drug interactions:**"]
        for it in interactions[:8]:
            sev = it.get("severity") or "?"
            out.append(f"- {it['drug_a']} ↔ {it['drug_b']} ({sev}): {it['description'][:200]}")
        return "\n".join(out)

    # The tool sync wrapper: run the coroutine in a private loop so callers
    # don't need to be async. Safe because LangGraph executes tools in a
    # thread pool already.
    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Caller is already in an event loop — use a nested-safe pattern.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
