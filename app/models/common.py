from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class HealthCheck(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="API version")
    services: Dict[str, str] = Field(default_factory=dict, description="Service health status")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-01T12:00:00Z",
                "version": "1.0.0",
                "services": {
                    "pinecone": "healthy",
                    "huggingface": "healthy",
                    "database": "healthy"
                }
            }
        }

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "File size exceeds limit",
                "details": {"max_size": "10MB", "provided_size": "15MB"},
                "timestamp": "2024-01-01T12:00:00Z",
                "request_id": "req_123456"
            }
        }

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="asc", description="Sort order (asc/desc)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

class WebSocketMessage(BaseModel):
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class APIKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="API key name")
    expires_in_days: Optional[int] = Field(default=30, ge=1, le=365, description="Expiry in days")

class APIKeyResponse(BaseModel):
    api_key: str = Field(..., description="Generated API key")
    name: str = Field(..., description="API key name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None, description="Expiry date")

class TokenUsage(BaseModel):
    prompt_tokens: int = Field(..., description="Tokens in prompt")
    completion_tokens: int = Field(..., description="Tokens in completion")
    total_tokens: int = Field(..., description="Total tokens used")
    estimated_cost: Optional[float] = Field(default=None, description="Estimated cost in USD")