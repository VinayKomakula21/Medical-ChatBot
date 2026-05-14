"""Unit tests for app.services.query_processor.

Pure deterministic logic — no external services, no mocks.
Verifies the heuristics that drive query decomposition and routing decisions
upstream (chat_groq, agent prompt construction).
"""
from __future__ import annotations

import pytest

from app.services.query_processor import QueryProcessor


@pytest.fixture
def qp() -> QueryProcessor:
    return QueryProcessor()


# ---------------------------------------------------------------------------
# is_complex_query — 2+ indicators trip it
# ---------------------------------------------------------------------------
class TestIsComplexQuery:
    def test_short_simple_question_is_not_complex(self, qp: QueryProcessor) -> None:
        assert qp.is_complex_query("What is pneumonia?") is False

    def test_single_and_alone_is_not_complex(self, qp: QueryProcessor) -> None:
        # Only 1 indicator — single ' and ' phrase, short length, no other signals.
        assert qp.is_complex_query("Salt and sugar.") is False

    def test_long_query_with_and_is_complex(self, qp: QueryProcessor) -> None:
        # Triggers ≥2 indicators: ' and ' + length > 15 words.
        q = (
            "What are the symptoms of pneumonia and how is it diagnosed "
            "in older adults with multiple co-morbidities?"
        )
        assert qp.is_complex_query(q) is True

    def test_multiple_question_marks_with_and_is_complex(
        self, qp: QueryProcessor
    ) -> None:
        q = "What is metformin? And what are its side effects?"
        assert qp.is_complex_query(q) is True

    def test_semicolon_separated_with_and_is_complex(self, qp: QueryProcessor) -> None:
        q = "Tell me about insulin; and about diabetes."
        assert qp.is_complex_query(q) is True

    def test_both_keyword_with_length_is_complex(self, qp: QueryProcessor) -> None:
        q = "Compare both metformin and insulin therapies for type 2 diabetes patients."
        assert qp.is_complex_query(q) is True


# ---------------------------------------------------------------------------
# classify_query_type — priority is emergency > symptom > treatment > diagnosis
#                       > prevention > general
# ---------------------------------------------------------------------------
class TestClassifyQueryType:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("I'm having chest pain, help!", "emergency"),
            ("Severe bleeding from my arm", "emergency"),
            ("This is an urgent question", "emergency"),
            ("What are the symptoms of flu?", "symptom"),
            ("Sign of stroke?", "symptom"),  # 'sign' is overridden by 'stroke' → emergency
            ("How do I know if I have anemia", "symptom"),
            ("How to treat headache", "treatment"),
            ("What medicine helps a sore throat", "treatment"),
            ("What is hypertension?", "diagnosis"),
            ("Explain diabetes", "diagnosis"),
            ("How to prevent heart disease", "prevention"),
            ("Hello there", "general"),
        ],
    )
    def test_classifies_canonical_queries(
        self, qp: QueryProcessor, query: str, expected: str
    ) -> None:
        # 'Sign of stroke?' contains 'stroke' which is an emergency keyword and
        # takes priority — adjust expectation accordingly.
        if "stroke" in query.lower():
            expected = "emergency"
        assert qp.classify_query_type(query) == expected

    def test_emergency_priority_over_symptom(self, qp: QueryProcessor) -> None:
        # Even with symptom keywords, an emergency keyword wins.
        assert qp.classify_query_type("symptom of heart attack") == "emergency"


# ---------------------------------------------------------------------------
# extract_medical_entities — returns flat lists per bucket
# ---------------------------------------------------------------------------
class TestExtractMedicalEntities:
    def test_returns_all_four_buckets(self, qp: QueryProcessor) -> None:
        out = qp.extract_medical_entities("")
        assert set(out.keys()) == {"conditions", "symptoms", "body_parts", "medications"}

    def test_extracts_condition_and_symptom_and_body_part(
        self, qp: QueryProcessor
    ) -> None:
        out = qp.extract_medical_entities("My head hurts from a flu fever")
        assert "flu" in out["conditions"]
        assert "fever" in out["symptoms"]
        assert "head" in out["body_parts"]

    def test_extracts_medication(self, qp: QueryProcessor) -> None:
        out = qp.extract_medical_entities("Can I take aspirin with ibuprofen?")
        assert {"aspirin", "ibuprofen"} <= set(out["medications"])

    def test_empty_query_yields_empty_lists(self, qp: QueryProcessor) -> None:
        out = qp.extract_medical_entities("")
        for v in out.values():
            assert v == []

    def test_is_case_insensitive(self, qp: QueryProcessor) -> None:
        out = qp.extract_medical_entities("DIABETES management")
        assert "diabetes" in out["conditions"]
