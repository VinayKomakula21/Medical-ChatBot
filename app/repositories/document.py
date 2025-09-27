"""
Document repository for managing document metadata and vectors.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings
from app.db.pinecone import get_index, add_documents, search_similar_documents
from app.repositories.base import BaseRepository
from app.services.embeddings import hf_embeddings


class DocumentRepository(BaseRepository):
    """
    Repository for managing documents and their vector embeddings.
    Interfaces with Pinecone for vector storage.
    """

    def __init__(self):
        super().__init__()
        # In-memory metadata storage
        # TODO: Replace with database storage
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._document_chunks: Dict[str, List[str]] = {}

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new document record."""
        doc_id = data.get("id") or str(uuid4())

        document = {
            "id": doc_id,
            "filename": data["filename"],
            "file_path": data.get("file_path"),
            "content_type": data.get("content_type", "text/plain"),
            "size": data.get("size", 0),
            "chunks_count": data.get("chunks_count", 0),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "indexed": False,
            "index_status": "pending"
        }

        self._documents[doc_id] = document
        self.logger.info(f"Created document record: {doc_id}")
        return document

    async def get(self, id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        return self._documents.get(id)

    async def update(self, id: str, data: Dict[str, Any]) -> bool:
        """Update document metadata."""
        if id not in self._documents:
            return False

        document = self._documents[id]
        document.update(data)
        document["updated_at"] = datetime.utcnow().isoformat()

        self.logger.info(f"Updated document: {id}")
        return True

    async def delete(self, id: str) -> bool:
        """Delete document and its vectors."""
        if id not in self._documents:
            return False

        # Delete from Pinecone if vectors exist
        try:
            await self.delete_vectors(id)
        except Exception as e:
            self.logger.error(f"Failed to delete vectors for document {id}: {e}")

        # Delete document record
        del self._documents[id]

        # Delete chunks if any
        if id in self._document_chunks:
            del self._document_chunks[id]

        # Delete file if exists
        document = self._documents.get(id)
        if document and document.get("file_path"):
            file_path = Path(document["file_path"])
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to delete file {file_path}: {e}")

        self.logger.info(f"Deleted document: {id}")
        return True

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """List documents with pagination and optional tag filtering."""
        documents = list(self._documents.values())

        # Filter by tags if provided
        if tags:
            documents = [
                doc for doc in documents
                if any(tag in doc.get("tags", []) for tag in tags)
            ]

        # Sort by created_at descending
        documents.sort(key=lambda x: x["created_at"], reverse=True)

        # Apply pagination
        return documents[skip : skip + limit]

    async def store_chunks(
        self,
        document_id: str,
        chunks: List[str]
    ) -> bool:
        """Store document chunks in memory."""
        self._document_chunks[document_id] = chunks

        # Update document record
        if document_id in self._documents:
            self._documents[document_id]["chunks_count"] = len(chunks)
            self._documents[document_id]["updated_at"] = datetime.utcnow().isoformat()

        self.logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
        return True

    async def get_chunks(self, document_id: str) -> List[str]:
        """Get chunks for a document."""
        return self._document_chunks.get(document_id, [])

    async def index_document(
        self,
        document_id: str,
        chunks: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Index document chunks in Pinecone."""
        try:
            if not chunks:
                self.logger.warning(f"No chunks to index for document {document_id}")
                return False

            # Prepare metadata for each chunk
            chunk_metadata = metadata or {}
            chunk_metadata["document_id"] = document_id

            # Add chunks to vector store
            chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [chunk_metadata.copy() for _ in chunks]

            # Store in Pinecone using the add_documents function
            add_documents(
                texts=chunks,
                ids=chunk_ids,
                metadatas=metadatas
            )

            # Update document status
            await self.update(document_id, {
                "indexed": True,
                "index_status": "completed",
                "indexed_at": datetime.utcnow().isoformat()
            })

            self.logger.info(f"Indexed {len(chunks)} chunks for document {document_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to index document {document_id}: {e}")
            await self.update(document_id, {
                "indexed": False,
                "index_status": f"failed: {str(e)}"
            })
            return False

    async def delete_vectors(self, document_id: str) -> bool:
        """Delete document vectors from Pinecone."""
        try:
            index = get_index()
            if not index:
                return False

            # Delete all chunks for this document
            # Pinecone doesn't support delete by metadata, so we need chunk IDs
            chunks = await self.get_chunks(document_id)
            if chunks:
                chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
                index.delete(ids=chunk_ids)
                self.logger.info(f"Deleted {len(chunk_ids)} vectors for document {document_id}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete vectors for document {document_id}: {e}")
            return False

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        filter_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity."""
        try:
            # Build filter if tags provided
            filter_dict = None
            if filter_tags:
                filter_dict = {"tags": {"$in": filter_tags}}

            # Search using the pinecone search function
            results = search_similar_documents(
                query=query,
                k=top_k,
                filter=filter_dict
            )

            # Format results
            formatted_results = []
            for result in results:
                formatted_result = {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("score", 0.0),
                    "document_id": result.get("metadata", {}).get("document_id")
                }

                # Add document info if available
                if formatted_result["document_id"] in self._documents:
                    formatted_result["document"] = self._documents[formatted_result["document_id"]]

                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            self.logger.error(f"Failed to search similar documents: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get document repository statistics."""
        total_documents = len(self._documents)
        indexed_documents = sum(1 for doc in self._documents.values() if doc.get("indexed"))
        total_chunks = sum(len(chunks) for chunks in self._document_chunks.values())

        tags = set()
        total_size = 0
        for doc in self._documents.values():
            tags.update(doc.get("tags", []))
            total_size += doc.get("size", 0)

        return {
            "total_documents": total_documents,
            "indexed_documents": indexed_documents,
            "total_chunks": total_chunks,
            "unique_tags": len(tags),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


# Singleton instance
document_repository = DocumentRepository()