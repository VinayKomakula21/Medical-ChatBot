"""
Hybrid Search Service - Combines vector similarity with BM25 keyword search.
Uses Reciprocal Rank Fusion (RRF) to merge results for better retrieval.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from rank_bm25 import BM25Okapi

from app.core import observability as obs
from app.core.config import settings
from app.db.pinecone import search_similar_documents
from app.services.reranker import get_reranker

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Hybrid search combining:
    1. Vector similarity search (Pinecone)
    2. BM25 keyword search (in-memory)

    Results are merged using Reciprocal Rank Fusion (RRF)
    """

    def __init__(self):
        self.bm25_index: Optional[BM25Okapi] = None
        self.documents: List[Dict[str, Any]] = []
        self.document_texts: List[str] = []
        self._rrf_k = 60  # RRF constant (default is 60)

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization for BM25.
        Lowercase, remove punctuation, split on whitespace.
        """
        # Lowercase and remove special characters
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        # Split and filter empty tokens
        tokens = [t.strip() for t in text.split() if t.strip()]
        return tokens

    def build_index(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build BM25 index from document chunks.

        Args:
            documents: List of dicts with 'id', 'content', and 'metadata' keys
        """
        if not documents:
            logger.warning("No documents provided for BM25 indexing")
            return

        self.documents = documents
        self.document_texts = [doc.get('content', '') for doc in documents]

        # Tokenize documents
        tokenized_docs = [self._tokenize(text) for text in self.document_texts]

        # Build BM25 index
        self.bm25_index = BM25Okapi(tokenized_docs)

        logger.info(f"Built BM25 index with {len(documents)} documents")

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to existing index (rebuilds index)."""
        self.documents.extend(documents)
        self.build_index(self.documents)

    def _bm25_search(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        """
        Search using BM25.

        Returns:
            List of (document_index, score) tuples sorted by score descending
        """
        if not self.bm25_index or not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25_index.get_scores(query_tokens)

        # Get indices sorted by score
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        return indexed_scores[:top_k]

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Tuple[int, float]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each ranking list

        Args:
            vector_results: Results from vector search with 'id' key
            bm25_results: List of (doc_index, score) from BM25
            k: RRF constant (default 60)

        Returns:
            Merged results sorted by fused score
        """
        fused_scores: Dict[str, float] = defaultdict(float)
        result_map: Dict[str, Dict[str, Any]] = {}

        # Add vector search results to fusion
        for rank, result in enumerate(vector_results):
            doc_id = result.get('id', str(rank))
            fused_scores[doc_id] += 1.0 / (k + rank + 1)
            result_map[doc_id] = result

        # Add BM25 results to fusion
        for rank, (doc_idx, bm25_score) in enumerate(bm25_results):
            if doc_idx < len(self.documents):
                doc = self.documents[doc_idx]
                doc_id = doc.get('id', f"bm25_{doc_idx}")

                fused_scores[doc_id] += 1.0 / (k + rank + 1)

                # Add to result map if not already present
                if doc_id not in result_map:
                    result_map[doc_id] = {
                        'id': doc_id,
                        'content': doc.get('content', ''),
                        'metadata': doc.get('metadata', {}),
                        'score': bm25_score,
                        'source': 'bm25'
                    }

        # Sort by fused score
        sorted_results = sorted(
            fused_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build final results
        final_results = []
        for doc_id, fused_score in sorted_results:
            if doc_id in result_map:
                result = result_map[doc_id].copy()
                result['fused_score'] = fused_score
                final_results.append(result)

        return final_results

    def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.5,
        filter: Optional[Dict[str, Any]] = None,
        trace: Any = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and BM25 results.

        Args:
            query: Search query string
            top_k: Number of results to return
            vector_weight: Weight for vector results (0-1, unused in RRF but kept for API)
            filter: Optional filter dict for vector search
            trace: optional Langfuse trace/span to nest retrieval under

        Returns:
            List of search results with fused scores
        """
        with obs.span(
            trace,
            name="hybrid_search",
            input={"query": query, "top_k": top_k},
        ) as ret_span:
            # If a reranker is configured we over-fetch from the retrieval
            # stage so the reranker has a richer pool to choose from. Falls
            # back to top_k * 3 when no reranker.
            reranker = get_reranker()
            wants_rerank = reranker.name != "noop"
            fetch_k = settings.RERANKER_FETCH_K if wants_rerank else top_k * 3
            vector_k = min(fetch_k, 50)

            try:
                vector_results = search_similar_documents(
                    query=query,
                    k=vector_k,
                    filter=filter
                )
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to BM25: {e}")
                vector_results = []

            # Get BM25 results
            bm25_results = self._bm25_search(query, top_k=vector_k)

            def _finalize(candidates: List[Dict[str, Any]], path: str) -> List[Dict[str, Any]]:
                """Rerank (if configured) then slice to top_k. Records path on span."""
                if wants_rerank and candidates:
                    with obs.span(
                        ret_span,
                        name=f"rerank.{reranker.name}",
                        input={"n_candidates": len(candidates), "top_k": top_k},
                    ) as rerank_span:
                        ranked = reranker.rerank(query, candidates, top_k=top_k)
                        try:
                            rerank_span.update(output={"n_returned": len(ranked)})
                        except Exception:  # noqa: BLE001
                            pass
                        out = ranked
                else:
                    out = candidates[:top_k]
                try:
                    ret_span.update(output={"path": path, "n_results": len(out)})
                except Exception:  # noqa: BLE001
                    pass
                return out

            # If no BM25 index, return vector results only (reranked)
            if not bm25_results:
                logger.debug("No BM25 results, returning vector results only")
                return _finalize(vector_results, path="vector_only")

            # If no vector results, convert BM25 to standard format (reranked)
            if not vector_results:
                logger.debug("No vector results, returning BM25 results only")
                results: List[Dict[str, Any]] = []
                for doc_idx, score in bm25_results[:vector_k]:
                    if doc_idx < len(self.documents):
                        doc = self.documents[doc_idx]
                        results.append({
                            'id': doc.get('id', f"bm25_{doc_idx}"),
                            'content': doc.get('content', ''),
                            'metadata': doc.get('metadata', {}),
                            'score': score,
                            'source': 'bm25'
                        })
                return _finalize(results, path="bm25_only")

            # Merge using RRF, then rerank top fetch_k → top_k
            fused_results = self._reciprocal_rank_fusion(
                vector_results,
                bm25_results,
                k=self._rrf_k
            )
            try:
                ret_span.update(metadata={
                    "n_vector": len(vector_results),
                    "n_bm25": len(bm25_results),
                    "n_fused": len(fused_results),
                })
            except Exception:  # noqa: BLE001
                pass
            return _finalize(fused_results, path="hybrid_rrf")

    def search_with_expansion(
        self,
        query: str,
        top_k: int = 10,
        expand_synonyms: bool = True,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search with optional query expansion.

        For medical terms, can expand with common synonyms.
        """
        # Basic medical synonyms for query expansion
        medical_synonyms = {
            'heart attack': ['myocardial infarction', 'cardiac arrest'],
            'high blood pressure': ['hypertension'],
            'sugar': ['glucose', 'diabetes'],
            'flu': ['influenza'],
            'cold': ['common cold', 'rhinitis'],
            'headache': ['migraine', 'cephalgia'],
            'stomach pain': ['abdominal pain', 'gastric pain'],
            'fever': ['pyrexia', 'high temperature'],
        }

        expanded_query = query

        if expand_synonyms:
            query_lower = query.lower()
            for term, synonyms in medical_synonyms.items():
                if term in query_lower:
                    # Add first synonym to expand query
                    expanded_query = f"{query} {synonyms[0]}"
                    break

        return self.search(expanded_query, top_k=top_k, filter=filter)

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "indexed_documents": len(self.documents),
            "has_bm25_index": self.bm25_index is not None,
            "rrf_constant": self._rrf_k
        }


# Singleton instance
hybrid_search_service = HybridSearchService()


def hybrid_search(
    query: str,
    top_k: int = 10,
    filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function for hybrid search.

    Falls back to pure vector search if BM25 index is not built.
    """
    return hybrid_search_service.search(query, top_k=top_k, filter=filter)
