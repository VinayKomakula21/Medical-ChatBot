"""
Document service for handling document upload, processing, and search.
Uses SQLAlchemy for persistent storage and supports background processing.
"""
import json
import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import asyncio
from concurrent.futures import ThreadPoolExecutor

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    InvalidFileFormatException,
    FileSizeLimitException,
    DocumentNotFoundException,
    VectorStoreException
)
from app.models.document import (
    DocumentUploadResponse,
    DocumentInfo,
    DocumentMetadata,
    DocumentDeleteResponse
)
from app.db.pinecone import add_documents, delete_documents, get_index_stats
from app.repositories.document import document_repository

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""]
        )
        self.executor = ThreadPoolExecutor(max_workers=2)

    def _validate_file(self, file: UploadFile) -> None:
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in settings.allowed_extensions_list:
            raise InvalidFileFormatException(file_ext)

        # Check file size
        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise FileSizeLimitException(settings.MAX_FILE_SIZE)

    async def _load_document(self, file_path: Path) -> List[Any]:
        file_ext = file_path.suffix.lower()

        if file_ext == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif file_ext in [".txt", ".md"]:
            loader = TextLoader(str(file_path))
        else:
            # For other formats, try text loader as default
            loader = TextLoader(str(file_path))

        try:
            documents = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                loader.load
            )
            return documents
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {e}")
            raise

    async def _process_document_async(
        self,
        document_id: str,
        file_path: Path,
        filename: str,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ):
        """Background task to process document and index in Pinecone."""
        # Create a new database session for background task
        from app.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                start_time = time.time()

                # Load and process document
                documents = await self._load_document(file_path)

                # Split documents into chunks
                text_chunks = self.text_splitter.split_documents(documents)

                # Prepare texts and metadata for indexing
                texts = [chunk.page_content for chunk in text_chunks]
                metadatas = []
                ids = []

                for i, chunk in enumerate(text_chunks):
                    chunk_id = f"{document_id}_{i}"
                    metadata = {
                        "document_id": str(document_id),
                        "filename": filename,
                        "chunk_index": i,
                        "total_chunks": len(text_chunks),
                        **(chunk.metadata or {})
                    }

                    if tags:
                        metadata["tags"] = tags
                    if custom_metadata:
                        metadata.update(custom_metadata)

                    metadatas.append(metadata)
                    ids.append(chunk_id)

                # Add to vector store
                add_documents(texts=texts, metadatas=metadatas, ids=ids)

                processing_time = time.time() - start_time

                # Update document with Pinecone IDs and mark as ready
                await document_repository.store_pinecone_ids(
                    db=db,
                    document_id=document_id,
                    pinecone_ids=ids,
                    chunks_count=len(text_chunks)
                )

                # Update processing time
                await document_repository.update(
                    db=db,
                    document_id=document_id,
                    processing_time=processing_time
                )

                await db.commit()
                logger.info(f"Document {document_id} processed successfully in {processing_time:.2f}s")

            except Exception as e:
                logger.error(f"Error processing document {document_id}: {e}")

                # Update status to failed
                await document_repository.update_status(
                    db=db,
                    document_id=document_id,
                    status="failed",
                    error_message=str(e)
                )
                await db.commit()

                # Clean up file on error
                file_path.unlink(missing_ok=True)

    async def upload_document(
        self,
        db: AsyncSession,
        file: UploadFile,
        background_tasks: Optional[BackgroundTasks] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> DocumentUploadResponse:
        """Upload document with optional background processing."""
        start_time = time.time()

        # Validate file
        self._validate_file(file)

        # Generate document ID
        document_id = str(uuid4())

        # Save file to disk
        file_ext = Path(file.filename).suffix.lower()
        file_path = settings.UPLOAD_DIR / f"{document_id}_{file.filename}"

        try:
            content = await file.read()
            file_size = len(content)

            with open(file_path, "wb") as f:
                f.write(content)

            # Create document record in database
            document = await document_repository.create(
                db=db,
                filename=file.filename,
                file_path=str(file_path),
                file_type=file_ext,
                file_size=file_size,
                user_id=user_id,
                tags=tags,
                custom_metadata=custom_metadata
            )

            # Use the generated document ID from the repository
            document_id = document.id

            if background_tasks:
                # Process in background
                background_tasks.add_task(
                    self._process_document_async,
                    document_id,
                    file_path,
                    file.filename,
                    tags,
                    custom_metadata
                )

                return DocumentUploadResponse(
                    document_id=UUID(document_id),
                    filename=file.filename,
                    file_size=file_size,
                    chunks_created=0,  # Will be updated after processing
                    processing_time=time.time() - start_time,
                    status="processing"
                )
            else:
                # Process synchronously
                documents = await self._load_document(file_path)
                text_chunks = self.text_splitter.split_documents(documents)

                # Prepare texts and metadata for indexing
                texts = [chunk.page_content for chunk in text_chunks]
                metadatas = []
                ids = []

                for i, chunk in enumerate(text_chunks):
                    chunk_id = f"{document_id}_{i}"
                    metadata = {
                        "document_id": str(document_id),
                        "filename": file.filename,
                        "chunk_index": i,
                        "total_chunks": len(text_chunks),
                        **(chunk.metadata or {})
                    }

                    if tags:
                        metadata["tags"] = tags
                    if custom_metadata:
                        metadata.update(custom_metadata)

                    metadatas.append(metadata)
                    ids.append(chunk_id)

                # Add to vector store
                try:
                    add_documents(texts=texts, metadatas=metadatas, ids=ids)
                except Exception as e:
                    # Clean up file and record if indexing fails
                    file_path.unlink(missing_ok=True)
                    await document_repository.delete(db, document_id)
                    raise VectorStoreException(f"Failed to index document: {str(e)}")

                processing_time = time.time() - start_time

                # Update document with Pinecone IDs
                await document_repository.store_pinecone_ids(
                    db=db,
                    document_id=document_id,
                    pinecone_ids=ids,
                    chunks_count=len(text_chunks)
                )

                await document_repository.update(
                    db=db,
                    document_id=document_id,
                    processing_time=processing_time
                )

                return DocumentUploadResponse(
                    document_id=UUID(document_id),
                    filename=file.filename,
                    file_size=file_size,
                    chunks_created=len(text_chunks),
                    processing_time=processing_time,
                    status="success"
                )

        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            # Clean up file on error
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise

    async def delete_document(
        self,
        db: AsyncSession,
        document_id: UUID
    ) -> DocumentDeleteResponse:
        """Delete document using stored Pinecone IDs (fixes the bug)."""
        doc_id_str = str(document_id)

        # Get document from database
        document = await document_repository.get(db, doc_id_str)
        if not document:
            raise DocumentNotFoundException(doc_id_str)

        # Get actual chunk count for response
        chunks_deleted = document.chunks_count or 0

        # Delete document (repository handles Pinecone deletion using stored IDs)
        success = await document_repository.delete(db, doc_id_str)

        if not success:
            raise DocumentNotFoundException(doc_id_str)

        return DocumentDeleteResponse(
            document_id=document_id,
            status="deleted",
            chunks_deleted=chunks_deleted
        )

    async def get_document_status(
        self,
        db: AsyncSession,
        document_id: str
    ) -> Dict[str, Any]:
        """Get document processing status."""
        document = await document_repository.get(db, document_id)
        if not document:
            raise DocumentNotFoundException(document_id)

        return {
            "document_id": document.id,
            "status": document.status,
            "filename": document.filename,
            "chunks_count": document.chunks_count,
            "processing_time": document.processing_time
        }

    async def list_documents(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List documents from database with pagination."""
        skip = (page - 1) * page_size

        # Get documents from database
        documents = await document_repository.list(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=page_size
        )

        # Get total count
        total = await document_repository.count(db=db, user_id=user_id)

        # Convert to response format
        doc_list = []
        for doc in documents:
            tags = []
            if doc.tags:
                try:
                    tags = json.loads(doc.tags)
                except json.JSONDecodeError:
                    pass

            doc_info = DocumentInfo(
                document_id=UUID(doc.id),
                metadata=DocumentMetadata(
                    filename=doc.filename,
                    file_type=doc.file_type,
                    file_size=doc.file_size,
                    created_at=doc.created_at.timestamp() if doc.created_at else 0,
                    tags=tags
                ),
                chunk_count=doc.chunks_count or 0,
                is_indexed=(doc.status == "ready")
            )
            doc_list.append(doc_info)

        return {
            "documents": doc_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        filter_tags: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search documents using vector similarity."""
        return await document_repository.search_similar(
            query=query,
            top_k=top_k,
            filter_tags=filter_tags,
            user_id=user_id
        )


# Singleton instance
document_service = DocumentService()
