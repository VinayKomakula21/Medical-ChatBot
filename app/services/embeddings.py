"""Embeddings — local sentence-transformers.

History: this service used to call the HuggingFace Inference API to avoid
local model load + mutex issues. HF restructured their inference routing
in 2025-2026 and the old free path now 404s. Migrated to a local
sentence-transformers model: same dimension (384), same model id, runs
in-process. Free, fast, more reliable.

Singleton `hf_embeddings` + method signatures preserved so call sites
(app/db/pinecone.py, app/services/document.py) don't change.
"""
from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import List

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class _LocalEmbeddings:
    """Local sentence-transformers embeddings.

    Thread-safe lazy load — the model is heavy (~90 MB for MiniLM); we load
    once on first use, then reuse the same SentenceTransformer instance from
    the executor threads that run_in_executor uses.
    """

    def __init__(self) -> None:
        self._model = None
        self._dimension = 384  # all-MiniLM-L6-v2
        self._lock = threading.Lock()

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    # Local import keeps cold-start fast for code paths that
                    # never embed (e.g. the agentic endpoint).
                    from sentence_transformers import SentenceTransformer
                    logger.info("Loading sentence-transformers model: %s", settings.EMBEDDING_MODEL)
                    self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                    # Update dimension from the actual model in case it's not MiniLM.
                    self._dimension = self._model.get_sentence_embedding_dimension() or 384
                    logger.info("Embeddings ready (dim=%d)", self._dimension)
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            model = self._get_model()
            vecs = model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
            return [v.astype(np.float32).tolist() for v in vecs]
        except Exception as exc:
            logger.error("embed_texts failed: %s", exc)
            return [[0.0] * self._dimension for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_single_cached(text)

    @lru_cache(maxsize=128)
    def _embed_single_cached(self, text: str) -> List[float]:
        try:
            model = self._get_model()
            vec = model.encode(
                text,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
            return vec.astype(np.float32).tolist()
        except Exception as exc:
            logger.error("Error embedding query: %s", exc)
            return [0.0] * self._dimension


# Singleton — same name the rest of the project uses.
hf_embeddings = _LocalEmbeddings()
