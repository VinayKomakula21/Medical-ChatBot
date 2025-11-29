"""
HuggingFace API-based Embeddings Service
Avoids local model loading and mutex lock issues
"""
import logging
import requests
import numpy as np
from typing import List, Optional
import time
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

class HFAPIEmbeddings:
    """
    Uses HuggingFace Inference API for embeddings
    No local model loading = No mutex lock issues
    """

    def __init__(self):
        # Using sentence-transformers/all-MiniLM-L6-v2 - reliable and available
        self.api_url = f"https://api-inference.huggingface.co/models/{settings.EMBEDDING_MODEL}"
        self.headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
        self.dimension = 384  # all-MiniLM-L6-v2 output dimension
        self._last_request_time = 0
        self._min_request_interval = 0.1  # Rate limiting: 100ms between requests

    def _wait_for_rate_limit(self):
        """Simple rate limiting for free tier"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts using HF API
        Returns list of embedding vectors
        """
        if not texts:
            return []

        embeddings = []
        batch_size = 5  # Process in small batches for free tier

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                self._wait_for_rate_limit()

                # Make API request
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json={"inputs": batch},
                    timeout=10
                )

                if response.status_code == 503:
                    # Model is loading, wait and retry
                    logger.info("Model is loading, waiting 20 seconds...")
                    time.sleep(20)
                    response = requests.post(
                        self.api_url,
                        headers=self.headers,
                        json={"inputs": batch},
                        timeout=10
                    )

                response.raise_for_status()
                batch_embeddings = response.json()

                # Handle single text vs batch response
                if isinstance(batch_embeddings[0][0], list):
                    # Batch response - take mean pooling
                    for emb in batch_embeddings:
                        embeddings.append(np.mean(emb, axis=0).tolist())
                else:
                    # Already pooled
                    embeddings.extend(batch_embeddings)

                logger.info(f"Embedded batch {i//batch_size + 1}, {len(batch)} texts")

            except requests.exceptions.Timeout:
                logger.error(f"Timeout embedding batch {i//batch_size + 1}")
                # Return zero vectors as fallback
                embeddings.extend([[0.0] * self.dimension] * len(batch))

            except Exception as e:
                logger.error(f"Error embedding texts: {e}")
                # Return zero vectors as fallback
                embeddings.extend([[0.0] * self.dimension] * len(batch))

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text
        Uses caching for repeated queries
        """
        return self._embed_single_cached(text)

    @lru_cache(maxsize=128)
    def _embed_single_cached(self, text: str) -> List[float]:
        """Cached version of single text embedding"""
        try:
            self._wait_for_rate_limit()

            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={"inputs": text},
                timeout=10
            )

            if response.status_code == 503:
                # Model is loading
                logger.info("Model is loading, waiting 20 seconds...")
                time.sleep(20)
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json={"inputs": text},
                    timeout=10
                )

            response.raise_for_status()
            embedding = response.json()

            # Handle response format
            if isinstance(embedding[0], list):
                # Need mean pooling
                return np.mean(embedding, axis=0).tolist()
            else:
                # Already pooled
                return embedding

        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            # Return zero vector as fallback
            return [0.0] * self.dimension

# Singleton instance
hf_embeddings = HFAPIEmbeddings()