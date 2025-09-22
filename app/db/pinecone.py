import logging
from typing import Optional, List, Dict, Any
from pinecone import Pinecone, ServerlessSpec

from app.core.config import settings
from app.services.embeddings import hf_embeddings

logger = logging.getLogger(__name__)

_pinecone_client: Optional[Pinecone] = None
_index = None

def init_pinecone() -> Pinecone:
    global _pinecone_client

    if _pinecone_client is None:
        try:
            _pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)

            # Check if index exists, create if not
            if settings.PINECONE_INDEX_NAME not in _pinecone_client.list_indexes().names():
                logger.info(f"Creating Pinecone index: {settings.PINECONE_INDEX_NAME}")
                _pinecone_client.create_index(
                    name=settings.PINECONE_INDEX_NAME,
                    dimension=settings.PINECONE_DIMENSION,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )
            logger.info("Pinecone client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    return _pinecone_client

def get_index():
    """Get Pinecone index directly"""
    global _index

    if _index is None:
        try:
            client = init_pinecone()
            _index = client.Index(settings.PINECONE_INDEX_NAME)
            logger.info("Pinecone index initialized successfully")
        except Exception as e:
            logger.error(f"Failed to get Pinecone index: {e}")
            raise

    return _index

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts using HF API"""
    try:
        return hf_embeddings.embed_texts(texts)
    except Exception as e:
        logger.error(f"Failed to embed texts: {e}")
        raise

def embed_query(text: str) -> List[float]:
    """Embed query using HF API"""
    try:
        return hf_embeddings.embed_query(text)
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        raise

def add_documents(
    texts: List[str],
    metadatas: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None
) -> List[str]:
    try:
        # Get embeddings using HF API
        embeddings = embed_texts(texts)

        # Prepare vectors for Pinecone
        index = get_index()
        vectors = []

        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            vector_id = ids[i] if ids else str(i)
            metadata = metadatas[i] if metadatas else {}
            metadata['text'] = text[:1000]  # Store truncated text in metadata

            vectors.append({
                'id': vector_id,
                'values': embedding,
                'metadata': metadata
            })

        # Upsert to Pinecone
        index.upsert(vectors=vectors)

        return ids if ids else [str(i) for i in range(len(texts))]
    except Exception as e:
        logger.error(f"Failed to add documents: {e}")
        raise

def search_similar_documents(
    query: str,
    k: int = 5,
    filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    try:
        # Get query embedding using HF API
        query_embedding = embed_query(query)

        # Search in Pinecone
        index = get_index()
        results = index.query(
            vector=query_embedding,
            top_k=k,
            filter=filter,
            include_metadata=True
        )

        # Format results
        formatted_results = []
        for match in results['matches']:
            formatted_results.append({
                "content": match['metadata'].get('text', ''),
                "metadata": match['metadata'],
                "score": match['score']
            })

        return formatted_results
    except Exception as e:
        logger.error(f"Failed to search documents: {e}")
        raise

def delete_documents(ids: List[str]) -> bool:
    try:
        pinecone = init_pinecone()
        index = pinecone.Index(settings.PINECONE_INDEX_NAME)
        index.delete(ids=ids)
        return True
    except Exception as e:
        logger.error(f"Failed to delete documents: {e}")
        raise

def get_index_stats() -> Dict[str, Any]:
    try:
        pinecone = init_pinecone()
        index = pinecone.Index(settings.PINECONE_INDEX_NAME)
        return index.describe_index_stats()
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        raise