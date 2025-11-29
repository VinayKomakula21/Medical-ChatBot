"""
Query Processor Service - Handles query analysis and decomposition.
Breaks complex queries into sub-queries for better retrieval.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
import requests
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryProcessor:
    """
    Query processor for analyzing and decomposing complex queries.

    Features:
    - Query complexity detection
    - Query decomposition into sub-queries
    - Query type classification
    - Medical entity extraction
    """

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"

    def is_complex_query(self, query: str) -> bool:
        """
        Detect if a query is complex and needs decomposition.

        Complex queries typically:
        - Have multiple question marks
        - Use conjunctions like "and", "also", "as well as"
        - Are long (>15 words)
        - Ask about multiple topics
        """
        indicators = [
            query.count('?') > 1,
            ' and ' in query.lower(),
            ' also ' in query.lower(),
            ' as well as ' in query.lower(),
            ' plus ' in query.lower(),
            len(query.split()) > 15,
            '; ' in query,  # Semicolon often separates questions
            ' both ' in query.lower(),
        ]

        # Query is complex if 2+ indicators are true
        return sum(indicators) >= 2

    def classify_query_type(self, query: str) -> str:
        """
        Classify the type of medical query.

        Returns one of:
        - 'symptom': Asking about symptoms
        - 'treatment': Asking about treatments/remedies
        - 'diagnosis': Asking about diagnosis/conditions
        - 'prevention': Asking about prevention
        - 'emergency': Urgent medical situation
        - 'general': General health question
        """
        query_lower = query.lower()

        # Emergency indicators
        emergency_keywords = [
            'emergency', 'urgent', 'immediately', '911',
            'chest pain', "can't breathe", 'severe bleeding',
            'heart attack', 'stroke', 'choking'
        ]
        if any(kw in query_lower for kw in emergency_keywords):
            return 'emergency'

        # Symptom queries
        symptom_patterns = [
            r'symptom', r'sign[s]? of', r'how do i know',
            r'what does .* feel like', r'is it normal'
        ]
        if any(re.search(p, query_lower) for p in symptom_patterns):
            return 'symptom'

        # Treatment queries
        treatment_patterns = [
            r'treat', r'cure', r'remedy', r'medicine',
            r'medication', r'drug', r'how to get rid',
            r'what can i take', r'what helps'
        ]
        if any(re.search(p, query_lower) for p in treatment_patterns):
            return 'treatment'

        # Diagnosis queries
        diagnosis_patterns = [
            r'what is', r'what are', r'define',
            r'explain', r'cause[sd]?', r'why do'
        ]
        if any(re.search(p, query_lower) for p in diagnosis_patterns):
            return 'diagnosis'

        # Prevention queries
        prevention_patterns = [
            r'prevent', r'avoid', r'reduce risk',
            r'protect', r'stop .* from'
        ]
        if any(re.search(p, query_lower) for p in prevention_patterns):
            return 'prevention'

        return 'general'

    def extract_medical_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract medical entities from query.

        Returns dict with:
        - conditions: Medical conditions mentioned
        - symptoms: Symptoms mentioned
        - body_parts: Body parts mentioned
        - medications: Medications mentioned
        """
        query_lower = query.lower()

        # Common medical conditions (simplified list)
        conditions = []
        condition_keywords = [
            'diabetes', 'hypertension', 'asthma', 'arthritis',
            'flu', 'cold', 'fever', 'infection', 'allergy',
            'migraine', 'anxiety', 'depression', 'cancer'
        ]
        for kw in condition_keywords:
            if kw in query_lower:
                conditions.append(kw)

        # Common symptoms
        symptoms = []
        symptom_keywords = [
            'pain', 'ache', 'fever', 'cough', 'fatigue',
            'nausea', 'dizziness', 'swelling', 'rash',
            'headache', 'sore throat', 'runny nose'
        ]
        for kw in symptom_keywords:
            if kw in query_lower:
                symptoms.append(kw)

        # Body parts
        body_parts = []
        body_part_keywords = [
            'head', 'chest', 'stomach', 'back', 'neck',
            'throat', 'knee', 'shoulder', 'arm', 'leg',
            'heart', 'lung', 'liver', 'kidney'
        ]
        for kw in body_part_keywords:
            if kw in query_lower:
                body_parts.append(kw)

        # Medications
        medications = []
        med_keywords = [
            'aspirin', 'ibuprofen', 'acetaminophen', 'tylenol',
            'advil', 'antibiotic', 'insulin', 'vitamin'
        ]
        for kw in med_keywords:
            if kw in query_lower:
                medications.append(kw)

        return {
            'conditions': conditions,
            'symptoms': symptoms,
            'body_parts': body_parts,
            'medications': medications
        }

    def decompose_query(self, query: str) -> List[str]:
        """
        Decompose a complex query into simpler sub-queries.

        Uses rule-based decomposition first, falls back to LLM if needed.
        """
        # Try rule-based decomposition first
        sub_queries = self._rule_based_decomposition(query)

        if sub_queries:
            logger.debug(f"Rule-based decomposition: {sub_queries}")
            return sub_queries

        # Fall back to LLM-based decomposition
        if self.groq_api_key:
            sub_queries = self._llm_decomposition(query)
            if sub_queries:
                logger.debug(f"LLM decomposition: {sub_queries}")
                return sub_queries

        # If all else fails, return original query
        return [query]

    def _rule_based_decomposition(self, query: str) -> List[str]:
        """
        Rule-based query decomposition.

        Handles common patterns like:
        - "What are X and Y?"
        - "Tell me about X. Also, what about Y?"
        """
        sub_queries = []

        # Split on common separators
        separators = [
            r'\?\s*(?:and|also|additionally)',  # "? And" or "? Also"
            r'\.\s*(?:and|also|additionally)',  # ". And" or ". Also"
            r';\s*',  # Semicolon
            r'\s+and\s+(?=what|how|why|when|where|can|does|is)',  # "and what/how/etc"
        ]

        for sep in separators:
            parts = re.split(sep, query, flags=re.IGNORECASE)
            if len(parts) > 1:
                # Clean up parts
                sub_queries = [p.strip() for p in parts if p.strip()]
                # Add question marks if missing
                sub_queries = [
                    q + '?' if not q.endswith('?') and not q.endswith('.') else q
                    for q in sub_queries
                ]
                break

        # Handle "X and Y" pattern for simple cases
        if not sub_queries:
            match = re.match(
                r'(?:what (?:are|is)|tell me about|explain)\s+(.+?)\s+and\s+(.+?)(?:\?|$)',
                query,
                re.IGNORECASE
            )
            if match:
                topic1, topic2 = match.groups()
                sub_queries = [
                    f"What is {topic1.strip()}?",
                    f"What is {topic2.strip()}?"
                ]

        return sub_queries

    def _llm_decomposition(self, query: str) -> List[str]:
        """
        Use LLM to decompose complex queries.
        """
        if not self.groq_api_key:
            return []

        try:
            prompt = f"""Break this medical question into 2-3 simpler, focused sub-questions.
Each sub-question should be answerable independently.
Return only the sub-questions, one per line.
No numbering, no explanations.

Question: {query}

Sub-questions:"""

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 150,
            }

            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                self.groq_url,
                headers=headers,
                json=payload,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse sub-queries from response
                sub_queries = []
                for line in content.strip().split('\n'):
                    line = line.strip()
                    # Remove common prefixes
                    line = re.sub(r'^[\d\.\-\*\)]+\s*', '', line)
                    if line and len(line) > 5:
                        # Add question mark if missing
                        if not line.endswith('?'):
                            line += '?'
                        sub_queries.append(line)

                return sub_queries[:3]  # Limit to 3 sub-queries

        except Exception as e:
            logger.warning(f"LLM decomposition failed: {e}")

        return []

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Full query processing pipeline.

        Returns:
            Dict with:
            - original_query: The input query
            - is_complex: Whether query is complex
            - query_type: Classification of query
            - entities: Extracted medical entities
            - sub_queries: List of sub-queries (if complex)
        """
        is_complex = self.is_complex_query(query)
        query_type = self.classify_query_type(query)
        entities = self.extract_medical_entities(query)

        sub_queries = [query]
        if is_complex:
            sub_queries = self.decompose_query(query)

        return {
            'original_query': query,
            'is_complex': is_complex,
            'query_type': query_type,
            'entities': entities,
            'sub_queries': sub_queries
        }


# Singleton instance
query_processor = QueryProcessor()


def process_query(query: str) -> Dict[str, Any]:
    """Convenience function for query processing."""
    return query_processor.process_query(query)


def decompose_if_complex(query: str) -> List[str]:
    """
    Return sub-queries if query is complex, otherwise return [query].
    """
    if query_processor.is_complex_query(query):
        return query_processor.decompose_query(query)
    return [query]
