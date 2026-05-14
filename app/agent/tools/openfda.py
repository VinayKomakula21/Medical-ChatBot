"""OpenFDA drug-label lookup tool — free, no auth.

Hits api.fda.gov/drug/label.json for a brand or generic name and returns the
most relevant fields: indications, dosage, warnings, adverse reactions.
"""

from __future__ import annotations

import logging

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_OPENFDA = "https://api.fda.gov/drug/label.json"
_TIMEOUT = 8.0
# Fields we ask for — keeps the LLM context tidy.
_FIELDS_OF_INTEREST = (
    "indications_and_usage",
    "dosage_and_administration",
    "contraindications",
    "warnings",
    "adverse_reactions",
)


@tool
def lookup_drug_openfda(drug_name: str) -> str:
    """Look up a drug's FDA label (indications, dosage, warnings, adverse reactions).

    Use this when the user asks about a specific medication — what it's for,
    how it's dosed, known side effects, or warnings. Free, authoritative
    source from the FDA.

    Args:
        drug_name: brand or generic name (e.g. "metformin" or "Lipitor")

    Returns:
        A structured summary of the FDA label, or a "not found" message.
    """
    # Search both brand and generic name fields.
    query = f'(openfda.brand_name:"{drug_name}" OR openfda.generic_name:"{drug_name}")'
    params = {"search": query, "limit": "1"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(_OPENFDA, params=params)
    except httpx.HTTPError as exc:
        logger.warning("OpenFDA transport error: %s", exc)
        return f"OpenFDA transport error: {exc}"

    if resp.status_code == 404:
        return f"No OpenFDA label found for: {drug_name}"
    if resp.status_code != 200:
        return f"OpenFDA error: HTTP {resp.status_code}"

    results = resp.json().get("results", [])
    if not results:
        return f"No OpenFDA label found for: {drug_name}"

    label = results[0]
    out: list[str] = [f"**{drug_name}** — FDA label summary:"]
    for field in _FIELDS_OF_INTEREST:
        vals = label.get(field) or []
        if not vals:
            continue
        # Each value is itself a long string; trim aggressively for LLM context.
        text = vals[0] if isinstance(vals, list) else str(vals)
        text = text[:600].replace("\n", " ").strip()
        pretty = field.replace("_", " ").title()
        out.append(f"- **{pretty}**: {text}")
    return "\n".join(out)
