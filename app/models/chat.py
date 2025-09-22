from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @validator("role")
    def validate_role(cls, v):
        if v not in ["user", "assistant", "system"]:
            raise ValueError("Role must be 'user', 'assistant', or 'system'")
        return v

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="User message")
    conversation_id: Optional[UUID] = Field(default=None, description="Conversation ID for context")
    stream: bool = Field(default=False, description="Enable streaming response")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="LLM temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=2048, description="Maximum response tokens")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What are the symptoms of diabetes?",
                "conversation_id": None,
                "stream": False,
                "temperature": 0.5
            }
        }

class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant response")
    conversation_id: UUID = Field(default_factory=uuid4, description="Conversation ID")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents")
    tokens_used: Optional[int] = Field(default=None, description="Tokens used in generation")
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Common symptoms of diabetes include increased thirst, frequent urination, extreme fatigue...",
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "sources": [
                    {
                        "document": "medical_guide.pdf",
                        "page": 42,
                        "relevance_score": 0.92
                    }
                ],
                "tokens_used": 256,
                "processing_time": 1.23
            }
        }

class ConversationHistory(BaseModel):
    conversation_id: UUID
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

class StreamingChatResponse(BaseModel):
    chunk: str = Field(..., description="Response chunk")
    conversation_id: UUID
    is_final: bool = Field(default=False, description="Whether this is the final chunk")
    sources: Optional[List[Dict[str, Any]]] = None