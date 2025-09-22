import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import asyncio
from concurrent.futures import ThreadPoolExecutor

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from fastapi import UploadFile

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
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileFormatException(file_ext)

        # Check file size
        if file.size > settings.MAX_FILE_SIZE:
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

    async def upload_document(
        self,
        file: UploadFile,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentUploadResponse:
        start_time = time.time()
        document_id = uuid4()

        # Validate file
        self._validate_file(file)

        # Save file to disk
        file_path = settings.UPLOAD_DIR / f"{document_id}_{file.filename}"
        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

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
                # Clean up file if indexing fails
                file_path.unlink(missing_ok=True)
                raise VectorStoreException(f"Failed to index document: {str(e)}")

            processing_time = time.time() - start_time

            return DocumentUploadResponse(
                document_id=document_id,
                filename=file.filename,
                file_size=file.size,
                chunks_created=len(text_chunks),
                processing_time=processing_time,
                status="success"
            )

        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            # Clean up file on error
            file_path.unlink(missing_ok=True)
            raise

    async def delete_document(self, document_id: UUID) -> DocumentDeleteResponse:
        try:
            # Get index stats to find chunks
            stats = get_index_stats()

            # In a real implementation, you'd query for chunks with this document_id
            # For now, we'll construct the chunk IDs
            chunk_ids = []
            for i in range(100):  # Assume max 100 chunks per document
                chunk_ids.append(f"{document_id}_{i}")

            # Delete from vector store
            delete_documents(chunk_ids)

            # Delete file from disk
            for file_path in settings.UPLOAD_DIR.glob(f"{document_id}_*"):
                file_path.unlink(missing_ok=True)

            return DocumentDeleteResponse(
                document_id=document_id,
                status="deleted",
                chunks_deleted=len(chunk_ids)
            )

        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise

    async def list_documents(
        self,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        # In a real implementation, this would query a database
        # For now, we'll list files from the upload directory
        documents = []

        try:
            files = sorted(
                settings.UPLOAD_DIR.glob("*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            for file_path in files[start_idx:end_idx]:
                # Extract document_id from filename
                parts = file_path.stem.split("_", 1)
                if len(parts) >= 1:
                    try:
                        document_id = UUID(parts[0])
                        stat = file_path.stat()

                        doc_info = DocumentInfo(
                            document_id=document_id,
                            metadata=DocumentMetadata(
                                filename=file_path.name.replace(f"{document_id}_", ""),
                                file_type="application/pdf",  # Would detect properly
                                file_size=stat.st_size,
                                created_at=stat.st_ctime,
                                tags=[]
                            ),
                            chunk_count=0,  # Would query vector store
                            is_indexed=True
                        )
                        documents.append(doc_info)
                    except ValueError:
                        continue

            return {
                "documents": documents,
                "total": len(files),
                "page": page,
                "page_size": page_size
            }

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            raise

    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        filter_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        from app.db.pinecone import search_similar_documents

        filter_dict = None
        if filter_tags:
            filter_dict = {"tags": {"$in": filter_tags}}

        try:
            results = search_similar_documents(
                query=query,
                k=top_k,
                filter=filter_dict
            )
            return results
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            raise VectorStoreException(f"Failed to search documents: {str(e)}")

# Singleton instance
document_service = DocumentService()