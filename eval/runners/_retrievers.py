"""Retrieval adapters for embedding-model comparison evals.

The production stack uses Pinecone. For Item #3 (embedding-model 3-way
comparison) we need to evaluate different embedding models against the same
corpus — but Pinecone's free tier locks the index dimension at creation time,
and three different models (MiniLM=384, PubMedBERT=768, BGE-large=1024) need
three different dims.

The free-tier path is **ChromaDB in-process**: each model gets its own
collection, embedded by sentence-transformers locally (no API calls), seeded
with the eval dataset's ground-truth contexts. The full eval suite then
points at this Chroma collection instead of Pinecone for the comparison run.

Production code paths are untouched — these adapters live entirely under eval/.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class Retriever(Protocol):
    """Minimal retriever interface — what _common.retrieve_contexts depends on."""

    name: str

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return [{id, content, metadata, score}, ...] — same shape as
        app.db.pinecone.search_similar_documents.
        """
        ...


# ---------------------------------------------------------------------------
# Pinecone — wraps the existing production path.
# ---------------------------------------------------------------------------
class PineconeRetriever:
    """Thin shim around app.db.pinecone.search_similar_documents.

    Embedding model is whatever the running service is configured for
    (settings.EMBEDDING_MODEL). For apples-to-apples comparison use the
    ChromaRetriever instead — Pinecone is here so eval runs can also exercise
    the actual production retrieval path.
    """

    name = "pinecone"

    def __init__(self) -> None:
        # lazy import keeps test/CI runs that don't need Pinecone import-clean
        from app.db.pinecone import search_similar_documents

        self._search = search_similar_documents

    def search(self, query: str, k: int = 5) -> list[dict]:
        try:
            return self._search(query=query, k=k) or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("PineconeRetriever search failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Chroma — local, per-model collections seeded with a passed corpus.
# ---------------------------------------------------------------------------
class ChromaRetriever:
    """In-process Chroma collection keyed on an HF sentence-transformers model.

    Lifecycle: construct → build_corpus(texts) once → search(...) repeatedly.
    Each instance owns one named collection; passing the same name + model
    reuses the existing cache.
    """

    name = "chroma"

    # Persistent path under eval/ so the embeddings cache survives across runs.
    _PERSIST_DIR = Path("eval/.chroma")

    def __init__(self, embed_model: str, collection_name: str) -> None:
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError as exc:
            raise SystemExit(
                "chromadb missing. Install with: pip install -r requirements.txt"
            ) from exc

        self.embed_model = embed_model
        self.collection_name = collection_name

        self._PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._PERSIST_DIR))
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embed_model)
        # get_or_create makes re-runs idempotent; rebuild_corpus() clears+rebuilds
        # for fresh measurements.
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
            metadata={"embed_model": embed_model},
        )
        logger.info(
            "Chroma collection ready: %s (embed_model=%s, n=%d)",
            collection_name,
            embed_model,
            self._collection.count(),
        )

    def rebuild_corpus(self, texts: Iterable[str]) -> int:
        """Wipe + re-add the corpus. Returns the number of texts indexed.

        We rebuild (rather than upsert) so embedding-model changes cannot leak
        stale vectors from a previous run.
        """
        # chromadb has no truncate; delete-then-recreate the collection.
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:  # noqa: BLE001
            pass
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._ef,
            metadata={"embed_model": self.embed_model},
        )

        unique_texts = list({t for t in texts if t and t.strip()})
        if not unique_texts:
            logger.warning("rebuild_corpus called with empty texts")
            return 0

        ids = [f"doc-{i}" for i in range(len(unique_texts))]
        self._collection.add(documents=unique_texts, ids=ids)
        logger.info(
            "Indexed %d docs into %s (embed_model=%s)",
            len(unique_texts),
            self.collection_name,
            self.embed_model,
        )
        return len(unique_texts)

    def search(self, query: str, k: int = 5) -> list[dict]:
        if self._collection.count() == 0:
            logger.warning("ChromaRetriever.search called before rebuild_corpus — empty result.")
            return []

        res = self._collection.query(query_texts=[query], n_results=k)
        docs: list[str] = (res.get("documents") or [[]])[0]
        ids: list[str] = (res.get("ids") or [[]])[0]
        # Chroma returns L2 distances by default — lower is better. Flip to a
        # similarity-shaped score so it lines up with Pinecone's cosine score.
        dists: list[float] = (res.get("distances") or [[]])[0]
        out: list[dict] = []
        for i, doc in enumerate(docs):
            score = 1.0 / (1.0 + dists[i]) if i < len(dists) else 0.0
            out.append(
                {
                    "id": ids[i] if i < len(ids) else f"doc-{i}",
                    "content": doc,
                    "metadata": {"embed_model": self.embed_model},
                    "score": score,
                    "source": "chroma",
                }
            )
        return out


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def build_retriever(
    kind: str,
    embed_model: str | None = None,
    collection_name: str | None = None,
) -> Retriever:
    """One-stop retriever factory used by CLI runners.

    kind="pinecone" → wraps production path; embed_model/collection ignored.
    kind="chroma"   → requires embed_model. collection_name defaults to a
                       slug of the model.
    """
    if kind == "pinecone":
        return PineconeRetriever()
    if kind == "chroma":
        if not embed_model:
            raise SystemExit("--embed-model required when --retriever=chroma")
        coll = collection_name or _slugify(embed_model)
        return ChromaRetriever(embed_model=embed_model, collection_name=coll)
    raise SystemExit(f"Unknown retriever kind: {kind!r} (expected: pinecone, chroma)")


def _slugify(name: str) -> str:
    return name.replace("/", "_").replace(".", "_").lower()
