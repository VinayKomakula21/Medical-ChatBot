"""SafetyService — layered post-generation guard for medical answers.

What it checks (all free-tier, no paid services):
  1. Scope refusal     — block "diagnose me / prescribe me" patterns; tag with
                         a "this isn't medical advice" preface.
  2. Emergency routing — extract the existing inline-in-chat_groq.py logic so
                         it's testable and reusable.
  3. Faithfulness      — claim-level grounding against retrieved chunks via a
                         cheap token-overlap heuristic. (Production RAGAS
                         faithfulness at runtime is on hold until #7b's
                         langchain bump unblocks RAGAS 0.2.)
  4. Multi-evidence    — optional MEGA-RAG-style rule: require ≥2 chunks
                         supporting a claim's key noun phrase.
  5. Drug-name check   — validate every drug-like token in the answer against
                         NIH RxNorm (free).

Returns SafetyVerdict — the chat service decides whether to block, annotate,
or pass through. v0 default: annotate (less disruptive than blocking).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.clients.rxnorm import rxnorm_client
from app.core.config import settings

logger = logging.getLogger(__name__)

# Patterns that should not get a diagnostic answer.
_OUT_OF_SCOPE = re.compile(
    r"\b(diagnose\s+me|am\s+i\s+(having|getting)|"
    r"prescribe\s+(me|for\s+me)|what\s+dosage\s+should\s+i\s+take|"
    r"is\s+it\s+safe\s+for\s+me\s+to\s+take)\b",
    re.IGNORECASE,
)

# Emergency-keyword set (extracted from chat_groq.py for reuse / testability).
EMERGENCY_KEYWORDS = (
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "trouble breathing",
    "severe bleeding",
    "stroke",
    "heart attack",
    "unconscious",
    "choking",
    "severe pain",
    "suicidal",
    "overdose",
)

EMERGENCY_PREFIX = (
    "🚨 **URGENT — If this is a medical emergency, call your local "
    "emergency number (911 in the US) immediately.** The information below "
    "is general guidance and not a substitute for emergency care.\n\n"
)

OUT_OF_SCOPE_PREFIX = (
    "ℹ️ **Note:** I can't diagnose or prescribe — that requires a clinician "
    "who knows you. The information below is general medical knowledge.\n\n"
)

LOW_CONFIDENCE_BANNER = (
    "\n\n⚠️ **Low confidence:** Some claims in this answer aren't strongly "
    "supported by the retrieved sources. Please verify with a healthcare "
    "professional or authoritative reference."
)

UNVERIFIED_DRUG_BANNER_TMPL = (
    "\n\n⚠️ **Couldn't verify drug names**: {names}. These weren't found in "
    "the NIH RxNorm database — they may be misspelled or fictional."
)


@dataclass
class SafetyVerdict:
    """Result of running SafetyService.check on a generated answer."""

    annotated_answer: str
    out_of_scope: bool = False
    is_emergency: bool = False
    faithfulness_score: float | None = None
    unverified_drugs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# Stopwords used by the faithfulness heuristic. Tiny on purpose.
_FAITHFULNESS_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "this",
        "these",
        "those",
        "but",
        "not",
        "no",
        "do",
        "does",
        "can",
        "may",
        "if",
        "when",
        "which",
        "what",
        "how",
        "your",
        "you",
        "their",
        "they",
        "them",
        "we",
        "our",
        "i",
    }
)

# Patterns that look like a drug name in a sentence: capitalized-ish words.
# This is a heuristic — RxNorm is the source of truth. The pattern just
# prefilters so we don't call the API for every word.
_DRUG_CANDIDATE = re.compile(r"\b([A-Z][a-z]{3,}(?:-[a-z]+)?)\b")


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _FAITHFULNESS_STOPWORDS}


class SafetyService:
    """Stateless post-generation guard.

    Per-call: minimal CPU, plus optional async RxNorm lookups (parallel). Safe
    to call from the hot path. All checks degrade to no-op on failure so the
    user always gets *some* answer.
    """

    async def check(
        self,
        question: str,
        retrieved_chunks: list[dict[str, Any]],
        answer: str,
    ) -> SafetyVerdict:
        verdict = SafetyVerdict(annotated_answer=answer)
        if not settings.SAFETY_ENABLED or not answer:
            return verdict

        # 1. Scope refusal
        if _OUT_OF_SCOPE.search(question):
            verdict.out_of_scope = True
            verdict.notes.append("Question matched out-of-scope pattern.")
            verdict.annotated_answer = OUT_OF_SCOPE_PREFIX + verdict.annotated_answer

        # 2. Emergency routing — prefix banner if the question signals urgency
        q_lower = question.lower()
        if any(kw in q_lower for kw in EMERGENCY_KEYWORDS):
            verdict.is_emergency = True
            if not verdict.annotated_answer.startswith("🚨"):
                verdict.annotated_answer = EMERGENCY_PREFIX + verdict.annotated_answer

        # 3. Faithfulness (cheap token-overlap heuristic vs retrieved chunks)
        context_tokens: set[str] = set()
        for c in retrieved_chunks:
            context_tokens |= _tokens(c.get("content", ""))
        answer_tokens = _tokens(answer)
        if answer_tokens and context_tokens:
            overlap = len(answer_tokens & context_tokens) / max(1, len(answer_tokens))
            verdict.faithfulness_score = round(overlap, 3)
            if overlap < settings.SAFETY_MIN_FAITHFULNESS:
                verdict.annotated_answer += LOW_CONFIDENCE_BANNER
                verdict.notes.append(
                    f"Faithfulness {overlap:.2f} below threshold "
                    f"{settings.SAFETY_MIN_FAITHFULNESS:.2f}"
                )

        # 4. Multi-evidence rule (optional, off by default)
        if settings.SAFETY_REQUIRE_MULTI_EVIDENCE and retrieved_chunks:
            chunk_token_sets = [_tokens(c.get("content", "")) for c in retrieved_chunks]
            # A claim is considered "supported" if its key noun (longest answer token)
            # appears in ≥2 chunks. Cheap proxy; ok for a v0.
            unsupported = []
            top_terms = sorted(answer_tokens, key=len, reverse=True)[:8]
            for term in top_terms:
                hits = sum(1 for s in chunk_token_sets if term in s)
                if hits < 2:
                    unsupported.append(term)
            if unsupported:
                verdict.notes.append(f"Single-evidence terms: {', '.join(unsupported[:5])}")

        # 5. Drug-name validation (async parallel calls to RxNorm)
        if settings.SAFETY_VALIDATE_DRUG_NAMES:
            candidates = self._extract_drug_candidates(answer)
            if candidates:
                unverified = await self._validate_drug_names(candidates)
                if unverified:
                    verdict.unverified_drugs = unverified
                    verdict.annotated_answer += UNVERIFIED_DRUG_BANNER_TMPL.format(
                        names=", ".join(unverified[:5])
                    )
                    verdict.notes.append(f"Unverified drug names: {', '.join(unverified[:5])}")

        return verdict

    @staticmethod
    def _extract_drug_candidates(answer: str) -> list[str]:
        """Heuristic prefilter — capitalized words ≥4 chars that aren't obvious
        non-drugs. RxNorm decides if they're real.
        """
        # Skip common non-drug capitalized words to save API calls.
        non_drug = {
            "Note",
            "Warning",
            "URGENT",
            "Symptoms",
            "Treatment",
            "Diagnosis",
            "Prevention",
            "When",
            "What",
            "How",
            "Common",
            "Severe",
            "Mild",
            "Chronic",
            "Acute",
            "Patient",
            "Patients",
            "Doctor",
            "Hospital",
            "Emergency",
            "Medical",
            "Health",
            "Healthcare",
            "Pain",
            "Fever",
            "Cancer",
            "Diabetes",
            "Asthma",
            "Heart",
            "Brain",
            "Lung",
            "Liver",
            "Kidney",
            "American",
            "European",
            "FDA",
            "CDC",
            "WHO",
            "NIH",
        }
        seen: list[str] = []
        for m in _DRUG_CANDIDATE.finditer(answer):
            w = m.group(1)
            if w in non_drug:
                continue
            if w in seen:
                continue
            seen.append(w)
            if len(seen) >= 8:
                break
        return seen

    @staticmethod
    async def _validate_drug_names(candidates: list[str]) -> list[str]:
        """Return the subset that RxNorm does NOT know about."""
        import asyncio as _asyncio

        async def _check(name: str) -> tuple[str, bool]:
            try:
                return name, await rxnorm_client.is_known_drug(name)
            except Exception:  # noqa: BLE001
                # Don't fail the whole answer because RxNorm flaked.
                return name, True  # assume valid on transport failure

        results = await _asyncio.gather(*(_check(c) for c in candidates))
        return [name for name, ok in results if not ok]


# Module-level singleton.
safety_service = SafetyService()
