import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.exceptions import (
    DocumentNotFoundException,
    FileSizeLimitException,
    InternalServerException,
    InvalidFileFormatException,
    ValidationException,
)
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
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    custom_metadata: Optional[str] = Form(None)
) -> DocumentUploadResponse:
    try:
        # Parse tags and metadata
        tag_list = tags.split(",") if tags else None
        metadata_dict = None
        if custom_metadata:
            try:
                metadata_dict = json.loads(custom_metadata)
            except json.JSONDecodeError:
                raise ValidationException("Invalid metadata JSON")

        response = await document_service.upload_document(
            file=file,
            tags=tag_list,
            custom_metadata=metadata_dict
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
    page_size: int = Query(20, ge=1, le=100)
) -> DocumentListResponse:
    try:
        result = await document_service.list_documents(
            page=page,
            page_size=page_size
        )
        return DocumentListResponse(**result)

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise InternalServerException(str(e))

@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(req: Request, document_id: str) -> DocumentDeleteResponse:
    try:
        from uuid import UUID
        doc_id = UUID(document_id)

        response = await document_service.delete_document(doc_id)
        return response

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except DocumentNotFoundException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise InternalServerException(str(e))

@router.post("/search")
async def search_documents(req: Request, request: DocumentSearchRequest) -> List[Dict[str, Any]]:
    try:
        results = await document_service.search_documents(
            query=request.query,
            top_k=request.top_k,
            filter_tags=request.filter_tags
        )
        return results

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise InternalServerException(str(e))

@router.get("/{document_id}/metadata")
async def get_document_metadata(req: Request, document_id: str) -> Dict[str, Any]:
    try:
        from uuid import UUID
        doc_id = UUID(document_id)

        # This would typically fetch from a database
        # For now, return a placeholder
        return {
            "document_id": document_id,
            "metadata": {
                "filename": "document.pdf",
                "file_type": "application/pdf",
                "file_size": 1024000,
                "page_count": 10,
                "created_at": "2024-01-01T00:00:00Z",
                "tags": ["medical", "research"]
            }
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        logger.error(f"Error fetching document metadata: {e}")
        raise InternalServerException(str(e))