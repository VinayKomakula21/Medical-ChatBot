import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.exceptions import (
    DocumentNotFoundException,
    FileSizeLimitException,
    InternalServerException,
    InvalidFileFormatException,
    ValidationException,
)
from app.db.database import get_db
from app.models.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentSearchRequest,
    DocumentUploadResponse,
)
from app.services.document import document_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    req: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    custom_metadata: Optional[str] = Form(None),
    async_processing: bool = Form(True),  # Enable background processing by default
    db: AsyncSession = Depends(get_db)
) -> DocumentUploadResponse:
    """
    Upload a document for processing.

    - **file**: PDF, TXT, or MD file to upload
    - **tags**: Comma-separated list of tags
    - **custom_metadata**: JSON string of additional metadata
    - **async_processing**: If true, process document in background (default: true)
    """
    try:
        # Parse tags and metadata
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        metadata_dict = None
        if custom_metadata:
            try:
                metadata_dict = json.loads(custom_metadata)
            except json.JSONDecodeError:
                raise ValidationException("Invalid metadata JSON")

        response = await document_service.upload_document(
            db=db,
            file=file,
            background_tasks=background_tasks if async_processing else None,
            tags=tag_list,
            custom_metadata=metadata_dict,
            user_id=None  # TODO: Get from current_user when auth is required
        )
        return response

    except InvalidFileFormatException as e:
        raise e
    except FileSizeLimitException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise InternalServerException(str(e))


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    req: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> DocumentListResponse:
    """List all uploaded documents with pagination."""
    try:
        result = await document_service.list_documents(
            db=db,
            page=page,
            page_size=page_size,
            user_id=None  # TODO: Get from current_user when auth is required
        )
        return DocumentListResponse(**result)

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise InternalServerException(str(e))


@router.get("/{document_id}/status")
async def get_document_status(
    req: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get document processing status.

    Returns:
    - **status**: "processing", "ready", or "failed"
    - **chunks_count**: Number of text chunks created (if ready)
    - **processing_time**: Time taken to process (if ready)
    """
    try:
        from uuid import UUID
        # Validate UUID format
        UUID(document_id)

        status = await document_service.get_document_status(db, document_id)
        return status

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except DocumentNotFoundException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching document status: {e}")
        raise InternalServerException(str(e))


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    req: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db)
) -> DocumentDeleteResponse:
    """Delete a document and its vectors from the database."""
    try:
        from uuid import UUID
        doc_id = UUID(document_id)

        response = await document_service.delete_document(db, doc_id)
        return response

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except DocumentNotFoundException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise InternalServerException(str(e))


@router.post("/search")
async def search_documents(
    req: Request,
    request: DocumentSearchRequest,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Search documents using vector similarity."""
    try:
        results = await document_service.search_documents(
            query=request.query,
            top_k=request.top_k,
            filter_tags=request.filter_tags,
            user_id=None  # TODO: Get from current_user when auth is required
        )
        return results

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise InternalServerException(str(e))


@router.get("/{document_id}/metadata")
async def get_document_metadata(
    req: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed metadata for a document."""
    try:
        from uuid import UUID
        from app.repositories.document import document_repository

        # Validate UUID format
        UUID(document_id)

        document = await document_repository.get(db, document_id)
        if not document:
            raise DocumentNotFoundException(document_id)

        # Parse tags if present
        tags = []
        if document.tags:
            try:
                tags = json.loads(document.tags)
            except json.JSONDecodeError:
                pass

        # Parse custom metadata if present
        custom_metadata = {}
        if document.custom_metadata:
            try:
                custom_metadata = json.loads(document.custom_metadata)
            except json.JSONDecodeError:
                pass

        return {
            "document_id": document.id,
            "metadata": {
                "filename": document.filename,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "page_count": document.page_count,
                "chunks_count": document.chunks_count,
                "status": document.status,
                "processing_time": document.processing_time,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "updated_at": document.updated_at.isoformat() if document.updated_at else None,
                "tags": tags,
                "custom_metadata": custom_metadata
            }
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except DocumentNotFoundException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching document metadata: {e}")
        raise InternalServerException(str(e))
