from pathlib import Path

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Medical ChatBot API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")
    DEBUG: bool = Field(default=False, env="DEBUG")

    # CORS settings - comma-separated string
    BACKEND_CORS_ORIGINS: str = Field(default="http://localhost:5173")

    # Pinecone settings
    PINECONE_API_KEY: str = Field(..., env="PINECONE_API_KEY")
    PINECONE_INDEX_NAME: str = Field(default="medicbot", env="PINECONE_INDEX_NAME")
    PINECONE_DIMENSION: int = Field(default=384, env="PINECONE_DIMENSION")

    # Groq settings
    GROQ_API_KEY: str | None = Field(default=None, env="GROQ_API_KEY")

    # HuggingFace settings
    HF_TOKEN: str = Field(..., env="HF_TOKEN")
    HF_MODEL_ID: str = Field(
        default="microsoft/phi-2",  # Changed to Phi-2 for efficiency
        env="HF_MODEL_ID",
    )
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",  # Using via API now
        env="EMBEDDING_MODEL",
    )

    # LLM settings
    LLM_TEMPERATURE: float = Field(default=0.5, env="LLM_TEMPERATURE")
    LLM_MAX_LENGTH: int = Field(default=512, env="LLM_MAX_LENGTH")

    # Document processing settings
    CHUNK_SIZE: int = Field(default=500, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=50, env="CHUNK_OVERLAP")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    ALLOWED_EXTENSIONS: str = Field(default=".pdf,.txt,.docx")

    # Upload settings
    UPLOAD_DIR: Path = Field(default=Path("uploads"), env="UPLOAD_DIR")

    # Database settings
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./medical_chatbot.db", env="DATABASE_URL"
    )

    # Security settings - JWT
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production-min-32-chars",
        env="SECRET_KEY",
        description="Secret key for JWT token signing (MUST change in production!)",
    )
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )  # 24 hours

    # Google OAuth settings
    GOOGLE_CLIENT_ID: str | None = Field(default=None, env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback", env="GOOGLE_REDIRECT_URI"
    )

    # Frontend URL for redirects after OAuth
    FRONTEND_URL: str = Field(default="http://localhost:5173", env="FRONTEND_URL")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT"
    )

    # Agentic mode (Item #9) — LangGraph + Groq tool-calling + free NIH/FDA tools
    AGENT_ENABLED: bool = Field(default=False, env="AGENT_ENABLED")
    AGENT_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        env="AGENT_MODEL",
        description="Groq tool-calling model. 70B handles multi-tool plans far better than 8B.",
    )
    AGENT_MAX_ITERATIONS: int = Field(default=6, env="AGENT_MAX_ITERATIONS")
    NCBI_API_KEY: str | None = Field(
        default=None,
        env="NCBI_API_KEY",
        description="Free key from https://www.ncbi.nlm.nih.gov/account/ — raises PubMed rate limit 3→10 req/s",
    )

    # Safety / hallucination guard (Item #6) — all free
    SAFETY_ENABLED: bool = Field(default=True, env="SAFETY_ENABLED")
    SAFETY_MIN_FAITHFULNESS: float = Field(
        default=0.6,
        env="SAFETY_MIN_FAITHFULNESS",
        description="Below this score we annotate the response with a low-confidence banner.",
    )
    SAFETY_REQUIRE_MULTI_EVIDENCE: bool = Field(
        default=False,
        env="SAFETY_REQUIRE_MULTI_EVIDENCE",
        description="MEGA-RAG-style: require ≥2 retrieved chunks supporting a claim.",
    )
    SAFETY_VALIDATE_DRUG_NAMES: bool = Field(
        default=True,
        env="SAFETY_VALIDATE_DRUG_NAMES",
        description="Check drug names mentioned in answers against RxNorm.",
    )

    # Reranker (Item #4) — free-tier: Jina v3 has a 10M-lifetime-token free key
    # grant per signup. RERANKER_PROVIDER=none keeps the project working with
    # no key configured. "bge" path is OSS local-self-host (commercial-safe).
    RERANKER_PROVIDER: str = Field(default="none", env="RERANKER_PROVIDER")
    RERANKER_TOP_K: int = Field(default=5, env="RERANKER_TOP_K")
    RERANKER_FETCH_K: int = Field(default=20, env="RERANKER_FETCH_K")
    JINA_API_KEY: str | None = Field(default=None, env="JINA_API_KEY")
    JINA_RERANKER_MODEL: str = Field(
        default="jina-reranker-v2-base-multilingual",
        env="JINA_RERANKER_MODEL",
        description="Jina rerank model id. Try 'jina-reranker-v3' for SOTA (token-pricier).",
    )

    # Observability (Langfuse) — free-tier
    # Cloud Hobby: 50k observations/mo. Self-hosted: no caps.
    # Off-by-default — set LANGFUSE_ENABLED=true plus the keys in .env to activate.
    LANGFUSE_ENABLED: bool = Field(default=False, env="LANGFUSE_ENABLED")
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None, env="LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: str | None = Field(default=None, env="LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = Field(default="https://us.cloud.langfuse.com", env="LANGFUSE_HOST")

    # Evaluation (RAGAS) — free-tier only
    # RAGAS uses LLM-as-judge; we route it through Groq (free tier) instead of OpenAI.
    # The judge LLM is intentionally larger than the production LLM
    # (llama-3.1-8b-instant) so the judge can fairly grade the smaller model's output.
    RAGAS_LLM_MODEL: str = Field(default="llama-3.3-70b-versatile", env="RAGAS_LLM_MODEL")
    # RAGAS embedding judge uses the same local model as production retrieval.
    # Local = no API calls = free.
    RAGAS_EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        env="RAGAS_EMBEDDING_MODEL",
    )
    EVAL_DATASET_PATH: str = Field(
        default="eval/dataset/medical_qa_eval.jsonl", env="EVAL_DATASET_PATH"
    )
    EVAL_SMOKE_DATASET_PATH: str = Field(
        default="eval/dataset/medical_qa_eval_smoke.jsonl",
        env="EVAL_SMOKE_DATASET_PATH",
    )
    EVAL_RESULTS_DIR: str = Field(default="eval/results", env="EVAL_RESULTS_DIR")
    EVAL_REPORTS_DIR: str = Field(default="eval/reports", env="EVAL_REPORTS_DIR")
    EVAL_FAITHFULNESS_THRESHOLD: float = Field(default=0.75, env="EVAL_FAITHFULNESS_THRESHOLD")
    EVAL_CONTEXT_PRECISION_THRESHOLD: float = Field(
        default=0.70, env="EVAL_CONTEXT_PRECISION_THRESHOLD"
    )
    EVAL_HIT_AT_5_THRESHOLD: float = Field(default=0.60, env="EVAL_HIT_AT_5_THRESHOLD")

    @validator("UPLOAD_DIR", pre=True)
    def create_upload_dir(cls, v):
        upload_path = Path(v)
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    @validator("SECRET_KEY")
    def secret_key_must_be_overridden_in_production(cls, v, values):
        """Refuse to boot in production with the placeholder JWT secret.

        Dev/test stay convenient; prod fails loud instead of shipping a
        guessable token-signing key.
        """
        placeholder = "your-secret-key-change-in-production-min-32-chars"
        if not values.get("DEBUG", False) and v == placeholder:
            raise ValueError(
                "SECRET_KEY is still the default placeholder. "
                "Set SECRET_KEY in .env (32+ random chars) before running with DEBUG=false."
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def retriever_k(self) -> int:
        return 3  # Number of documents to retrieve

    @property
    def is_production(self) -> bool:
        return not self.DEBUG

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Parse allowed extensions from comma-separated string"""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()]


settings = Settings()
