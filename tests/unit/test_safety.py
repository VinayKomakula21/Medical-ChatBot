"""Unit tests for app.services.safety.

Goal: verify the deterministic safety layers (scope, emergency, faithfulness,
drug-name extraction) without touching RxNorm. Drug validation is disabled
via settings so no network calls fire.
"""
from __future__ import annotations

import pytest

from app.services import safety as safety_mod
from app.services.safety import SafetyService


@pytest.fixture
def svc() -> SafetyService:
    return SafetyService()


@pytest.fixture(autouse=True)
def _no_rxnorm(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests focus on local logic — never let SafetyService call RxNorm.
    monkeypatch.setattr(safety_mod.settings, "SAFETY_VALIDATE_DRUG_NAMES", False)
    monkeypatch.setattr(safety_mod.settings, "SAFETY_ENABLED", True)


# ---------------------------------------------------------------------------
# _extract_drug_candidates — capitalized words ≥4 chars, minus common stop-set
# ---------------------------------------------------------------------------
class TestExtractDrugCandidates:
    def test_picks_up_capitalized_drug_words(self) -> None:
        out = SafetyService._extract_drug_candidates(
            "Patients are usually prescribed Metformin or Lipitor."
        )
        # Both are capitalized, both ≥4 chars, neither in non_drug set.
        assert "Metformin" in out
        assert "Lipitor" in out

    def test_skips_common_non_drug_capitalized_words(self) -> None:
        out = SafetyService._extract_drug_candidates(
            "Note: Patients with Diabetes should consult their Doctor."
        )
        # All of these are in the non_drug skip set.
        assert "Note" not in out
        assert "Patients" not in out
        assert "Diabetes" not in out
        assert "Doctor" not in out

    def test_dedupes_within_one_call(self) -> None:
        out = SafetyService._extract_drug_candidates("Metformin works. Metformin again.")
        assert out.count("Metformin") == 1

    def test_caps_at_eight_candidates(self) -> None:
        text = " ".join(f"Drug{i:02d}name" for i in range(15))
        # Force them to match the capitalized pattern with ≥4 chars.
        out = SafetyService._extract_drug_candidates(text)
        assert len(out) <= 8

    def test_empty_text_returns_empty(self) -> None:
        assert SafetyService._extract_drug_candidates("") == []


# ---------------------------------------------------------------------------
# check() — scope refusal & emergency routing
# ---------------------------------------------------------------------------
class TestScopeAndEmergency:
    @pytest.mark.asyncio
    async def test_out_of_scope_question_prepends_banner(self, svc: SafetyService) -> None:
        verdict = await svc.check(
            question="Can you diagnose me with diabetes?",
            retrieved_chunks=[],
            answer="Sure, your symptoms suggest type 2 diabetes.",
        )
        assert verdict.out_of_scope is True
        assert "can't diagnose" in verdict.annotated_answer.lower()

    @pytest.mark.asyncio
    async def test_in_scope_question_does_not_set_oos(self, svc: SafetyService) -> None:
        verdict = await svc.check(
            question="What is hypertension?",
            retrieved_chunks=[],
            answer="Hypertension is high blood pressure.",
        )
        assert verdict.out_of_scope is False

    @pytest.mark.asyncio
    async def test_emergency_keyword_prepends_urgent_banner(
        self, svc: SafetyService
    ) -> None:
        verdict = await svc.check(
            question="I'm having chest pain right now",
            retrieved_chunks=[],
            answer="Sit down and breathe slowly.",
        )
        assert verdict.is_emergency is True
        assert verdict.annotated_answer.startswith("🚨")

    @pytest.mark.asyncio
    async def test_non_emergency_does_not_prepend(self, svc: SafetyService) -> None:
        verdict = await svc.check(
            question="What helps with mild headache?",
            retrieved_chunks=[],
            answer="Rest and hydration usually help.",
        )
        assert verdict.is_emergency is False
        assert not verdict.annotated_answer.startswith("🚨")


# ---------------------------------------------------------------------------
# check() — faithfulness token-overlap heuristic
# ---------------------------------------------------------------------------
class TestFaithfulness:
    @pytest.mark.asyncio
    async def test_high_overlap_yields_high_score(self, svc: SafetyService) -> None:
        chunks = [{
            "content": (
                "Metformin is a first-line treatment for type 2 diabetes mellitus "
                "and lowers hepatic glucose production."
            )
        }]
        answer = "Metformin treats type 2 diabetes by lowering glucose production."
        verdict = await svc.check("How does metformin work?", chunks, answer)
        assert verdict.faithfulness_score is not None
        assert verdict.faithfulness_score >= 0.6

    @pytest.mark.asyncio
    async def test_zero_overlap_adds_low_confidence_banner(
        self, svc: SafetyService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Raise the threshold so even moderate-overlap scenarios fail.
        monkeypatch.setattr(safety_mod.settings, "SAFETY_MIN_FAITHFULNESS", 0.95)
        chunks = [{"content": "Apples grow on trees."}]
        answer = "Metformin treats diabetes."
        verdict = await svc.check("How does metformin work?", chunks, answer)
        assert verdict.faithfulness_score is not None
        assert verdict.faithfulness_score < 0.95
        assert "Low confidence" in verdict.annotated_answer

    @pytest.mark.asyncio
    async def test_disabled_safety_passes_answer_through(
        self, svc: SafetyService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(safety_mod.settings, "SAFETY_ENABLED", False)
        verdict = await svc.check(
            question="diagnose me please",  # would normally be flagged
            retrieved_chunks=[],
            answer="raw answer",
        )
        assert verdict.annotated_answer == "raw answer"
        assert verdict.out_of_scope is False
