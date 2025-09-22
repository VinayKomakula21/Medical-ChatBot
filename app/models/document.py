from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pathlib import Path

class DocumentMetadata(BaseModel):
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File MIME type")
    file_size: int = Field(..., description="File size in bytes")
    page_count: Optional[int] = Field(default=None, description="Number of pages (for PDFs)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list, description="Document tags")
    custom_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Custom metadata")

class DocumentUploadRequest(BaseModel):
    tags: Optional[List[str]] = Field(default=None, description="Tags for the document")
    custom_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Custom metadata")

class DocumentUploadResponse(BaseModel):
    document_id: UUID = Field(default_factory=uuid4, description="Unique document identifier")
    filename: str = Field(..., description="Uploaded filename")
    file_size: int = Field(..., description="File size in bytes")
    chunks_created: int = Field(..., description="Number of text chunks created")
    processing_time: float = Field(..., description="Processing time in seconds")
    status: str = Field(default="success", description="Upload status")

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "medical_guide.pdf",
                "file_size": 1024000,
                "chunks_created": 45,
                "processing_time": 2.5,
                "status": "success"
            }
        }

class DocumentInfo(BaseModel):
    document_id: UUID
    metadata: DocumentMetadata
    chunk_count: int = Field(..., description="Number of chunks in vector store")
    is_indexed: bool = Field(default=True, description="Whether document is indexed")

class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int = Field(..., description="Total number of documents")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Items per page")

class DocumentDeleteResponse(BaseModel):
    document_id: UUID
    status: str = Field(..., description="Deletion status")
    chunks_deleted: int = Field(..., description="Number of chunks deleted")

class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    filter_tags: Optional[List[str]] = Field(default=None, description="Filter by tags")

class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: UUID = Field(..., description="Parent document ID")
    content: str = Field(..., description="Chunk text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Relevance score")