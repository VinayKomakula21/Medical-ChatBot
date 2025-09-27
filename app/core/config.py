from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import os
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "Medical ChatBot API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")
    DEBUG: bool = Field(default=False, env="DEBUG")

    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
        env="BACKEND_CORS_ORIGINS"
    )

    # Pinecone settings
    PINECONE_API_KEY: str = Field(..., env="PINECONE_API_KEY")
    PINECONE_INDEX_NAME: str = Field(default="medicbot", env="PINECONE_INDEX_NAME")
    PINECONE_DIMENSION: int = Field(default=384, env="PINECONE_DIMENSION")

    # Groq settings
    GROQ_API_KEY: Optional[str] = Field(default=None, env="GROQ_API_KEY")

    # HuggingFace settings
    HF_TOKEN: str = Field(..., env="HF_TOKEN")
    HF_MODEL_ID: str = Field(
        default="microsoft/phi-2",  # Changed to Phi-2 for efficiency
        env="HF_MODEL_ID"
    )
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",  # Using via API now
        env="EMBEDDING_MODEL"
    )

    # LLM settings
    LLM_TEMPERATURE: float = Field(default=0.5, env="LLM_TEMPERATURE")
    LLM_MAX_LENGTH: int = Field(default=512, env="LLM_MAX_LENGTH")

    # Document processing settings
    CHUNK_SIZE: int = Field(default=500, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=50, env="CHUNK_OVERLAP")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".pdf", ".txt", ".docx"],
        env="ALLOWED_EXTENSIONS"
    )

    # Upload settings
    UPLOAD_DIR: Path = Field(
        default=Path("uploads"),
        env="UPLOAD_DIR"
    )

    # Security settings
    SECRET_KEY: str = Field(
        default="your-secret-key-here-change-in-production",
        env="SECRET_KEY"
    )
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @validator("UPLOAD_DIR", pre=True)
    def create_upload_dir(cls, v):
        upload_path = Path(v)
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def retriever_k(self) -> int:
        return 3  # Number of documents to retrieve

    @property
    def is_production(self) -> bool:
        return not self.DEBUG

settings = Settings()