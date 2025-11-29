"""
Document repository for managing document metadata and vectors.
Uses SQLAlchemy for persistent storage.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Document
from app.db.pinecone import get_index, add_documents, search_similar_documents, delete_documents
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    """
    Repository for managing documents and their vector embeddings.
    Uses SQLAlchemy for persistent storage and interfaces with Pinecone for vectors.
    """

    def __init__(self):
        super().__init__()

    async def create(
        self,
        db: AsyncSession,
        filename: str,
        file_path: str,
        file_type: str,
        file_size: int,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Create a new document record."""
        doc_id = str(uuid4())

        document = Document(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            status="processing",
            tags=json.dumps(tags) if tags else None,
            custom_metadata=json.dumps(custom_metadata) if custom_metadata else None
        )

        db.add(document)
        await db.flush()

        self.logger.info(f"Created document record: {doc_id}")
        return document

    async def get(
        self,
        db: AsyncSession,
        document_id: str
    ) -> Optional[Document]:
        """Get document by ID."""
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        document_id: str,
        **kwargs
    ) -> bool:
        """Update document metadata."""
        document = await self.get(db, document_id)
        if not document:
            return False

        # Update allowed fields
        allowed_fields = [
            'status', 'chunks_count', 'page_count', 'pinecone_ids',
            'tags', 'custom_metadata', 'processing_time'
        ]

        for field, value in kwargs.items():
            if field in allowed_fields:
                if field in ['tags', 'custom_metadata', 'pinecone_ids'] and not isinstance(value, str):
                    value = json.dumps(value)
                setattr(document, field, value)

        document.updated_at = datetime.utcnow()
        await db.flush()

        self.logger.info(f"Updated document: {document_id}")
        return True

    async def delete(
        self,
        db: AsyncSession,
        document_id: str
    ) -> bool:
        """Delete document, its vectors from Pinecone, and file from disk."""
        document = await self.get(db, document_id)
        if not document:
            return False

        # Delete vectors from Pinecone using stored IDs
        try:
            await self.delete_vectors(document)
        except Exception as e:
            self.logger.error(f"Failed to delete vectors for document {document_id}: {e}")

        # Delete file from disk
        if document.file_path:
            file_path = Path(document.file_path)
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to delete file {file_path}: {e}")

        # Delete document record
        await db.delete(document)
        await db.flush()

        self.logger.info(f"Deleted document: {document_id}")
        return True

    async def list(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None
    ) -> List[Document]:
        """List documents with pagination and optional filtering."""
        query = select(Document).order_by(Document.created_at.desc())

        if user_id:
            query = query.where(Document.user_id == user_id)

        if status:
            query = query.where(Document.status == status)

        # Tag filtering (documents with any of the provided tags)
        if tags:
            # Use JSON contains for tag filtering
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(Document.tags.contains(f'"{tag}"'))
            if tag_conditions:
                from sqlalchemy import or_
                query = query.where(or_(*tag_conditions))

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """Count documents with optional filtering."""
        query = select(func.count(Document.id))

        if user_id:
            query = query.where(Document.user_id == user_id)

        if status:
            query = query.where(Document.status == status)

        result = await db.execute(query)
        return result.scalar() or 0

    async def update_status(
        self,
        db: AsyncSession,
        document_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update document processing status."""
        document = await self.get(db, document_id)
        if not document:
            return False

        document.status = status
        if error_message:
            # Store error in custom_metadata
            metadata = json.loads(document.custom_metadata or '{}')
            metadata['error'] = error_message
            document.custom_metadata = json.dumps(metadata)

        document.updated_at = datetime.utcnow()
        await db.flush()

        self.logger.info(f"Updated document {document_id} status to {status}")
        return True

    async def store_pinecone_ids(
        self,
        db: AsyncSession,
        document_id: str,
        pinecone_ids: List[str],
        chunks_count: int
    ) -> bool:
        """Store Pinecone vector IDs after successful indexing."""
        document = await self.get(db, document_id)
        if not document:
            return False

        document.pinecone_ids = json.dumps(pinecone_ids)
        document.chunks_count = chunks_count
        document.status = "ready"
        document.updated_at = datetime.utcnow()

        await db.flush()

        self.logger.info(f"Stored {len(pinecone_ids)} Pinecone IDs for document {document_id}")
        return True

    async def delete_vectors(self, document: Document) -> bool:
        """Delete document vectors from Pinecone using stored IDs."""
        try:
            if not document.pinecone_ids:
                # Fallback: try to construct IDs from document_id and chunks_count
                if document.chunks_count and document.chunks_count > 0:
                    chunk_ids = [f"{document.id}_{i}" for i in range(document.chunks_count)]
                else:
                    self.logger.warning(f"No Pinecone IDs found for document {document.id}")
                    return False
            else:
                # Use stored Pinecone IDs (proper way)
                chunk_ids = json.loads(document.pinecone_ids)

            if chunk_ids:
                delete_documents(chunk_ids)
                self.logger.info(f"Deleted {len(chunk_ids)} vectors for document {document.id}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete vectors for document {document.id}: {e}")
            return False

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        filter_tags: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity."""
        try:
            # Build filter if tags or user_id provided
            filter_dict = {}
            if filter_tags:
                filter_dict["tags"] = {"$in": filter_tags}
            if user_id:
                filter_dict["user_id"] = user_id

            # Search using the pinecone search function
            results = search_similar_documents(
                query=query,
                k=top_k,
                filter=filter_dict if filter_dict else None
            )

            return results

        except Exception as e:
            self.logger.error(f"Failed to search similar documents: {e}")
            return []

    async def get_statistics(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get document repository statistics."""
        query_base = select(Document)
        if user_id:
            query_base = query_base.where(Document.user_id == user_id)

        # Get all documents for user
        result = await db.execute(query_base)
        documents = list(result.scalars().all())

        total_documents = len(documents)
        ready_documents = sum(1 for doc in documents if doc.status == "ready")
        processing_documents = sum(1 for doc in documents if doc.status == "processing")
        failed_documents = sum(1 for doc in documents if doc.status == "failed")
        total_chunks = sum(doc.chunks_count or 0 for doc in documents)

        tags = set()
        total_size = 0
        for doc in documents:
            if doc.tags:
                try:
                    doc_tags = json.loads(doc.tags)
                    tags.update(doc_tags)
                except json.JSONDecodeError:
                    pass
            total_size += doc.file_size or 0

        return {
            "total_documents": total_documents,
            "ready_documents": ready_documents,
            "processing_documents": processing_documents,
            "failed_documents": failed_documents,
            "total_chunks": total_chunks,
            "unique_tags": len(tags),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }

    def get_tags_list(self, document: Document) -> List[str]:
        """Helper to get tags as a list from document."""
        if document.tags:
            try:
                return json.loads(document.tags)
            except json.JSONDecodeError:
                return []
        return []

    def get_pinecone_ids_list(self, document: Document) -> List[str]:
        """Helper to get Pinecone IDs as a list from document."""
        if document.pinecone_ids:
            try:
                return json.loads(document.pinecone_ids)
            except json.JSONDecodeError:
                return []
        return []


# Singleton instance - now requires db session to be passed to methods
document_repository = DocumentRepository()
