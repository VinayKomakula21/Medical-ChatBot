"""Free NIH RxNorm / RxNav client — drug name validation & interactions.

RxNorm is a public NIH API. Free, no auth, no documented monthly cap.
Used by:
  - app/services/safety.py — validates that drug names mentioned in answers
    actually resolve to a real concept (rule-out hallucinated drug names).
  - app/agent/tools/rxnorm.py (Item #9) — drug-interaction tool for the agent.

Endpoints used here:
  - /REST/drugs.json?name=<x>          → looks up concept by name
  - /REST/rxcui.json?name=<x>          → returns RXCUI (concept id) or empty
  - /interaction/list.json?rxcuis=...  → drug-drug interactions for a CSV of rxcuis
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://rxnav.nlm.nih.gov/REST"
_TIMEOUT = 5.0


class RxNormClient:
    """Thin async wrapper around RxNav. One AsyncClient reused across calls."""

    def __init__(self, timeout: float = _TIMEOUT) -> None:
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def find_rxcui(self, name: str) -> str | None:
        """Look up a drug name → RXCUI (concept id). Returns None if unknown."""
        if not name or not name.strip():
            return None
        client = await self._get_client()
        try:
            resp = await client.get(f"{_BASE}/rxcui.json", params={"name": name})
        except httpx.HTTPError as exc:
            logger.warning("rxnorm.find_rxcui transport error for %r: %s", name, exc)
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
            ids = data.get("idGroup", {}).get("rxnormId", [])
            return ids[0] if ids else None
        except (ValueError, KeyError, IndexError):
            return None

    async def is_known_drug(self, name: str) -> bool:
        """Quick yes/no — used by SafetyService."""
        return await self.find_rxcui(name) is not None

    async def list_interactions(self, rxcuis: list[str]) -> list[dict[str, Any]]:
        """List drug-drug interactions for a list of RXCUIs.

        Returns a flat list of {drug_a, drug_b, severity, description} dicts.
        Empty list when the API returns no interactions (or fails).
        """
        if len(rxcuis) < 2:
            return []
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{_BASE}/interaction/list.json",
                params={"rxcuis": "+".join(rxcuis)},
            )
        except httpx.HTTPError as exc:
            logger.warning("rxnorm.list_interactions transport error: %s", exc)
            return []
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []

        out: list[dict[str, Any]] = []
        groups = data.get("fullInteractionTypeGroup", []) or []
        for grp in groups:
            for ft in grp.get("fullInteractionType", []) or []:
                pairs = ft.get("interactionPair", []) or []
                for pair in pairs:
                    concepts = pair.get("interactionConcept", []) or []
                    if len(concepts) < 2:
                        continue
                    out.append(
                        {
                            "drug_a": concepts[0].get("minConceptItem", {}).get("name", ""),
                            "drug_b": concepts[1].get("minConceptItem", {}).get("name", ""),
                            "severity": pair.get("severity", ""),
                            "description": pair.get("description", ""),
                        }
                    )
        return out


# Module-level singleton — avoid creating a new httpx client per call.
rxnorm_client = RxNormClient()
