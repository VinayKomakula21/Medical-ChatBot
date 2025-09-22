from fastapi import APIRouter, HTTPException
import logging
import asyncio
from datetime import datetime

from app.models.common import HealthCheck
from app.core.config import settings
from app.db.pinecone import get_index_stats

logger = logging.getLogger(__name__)
router = APIRouter()

async def check_pinecone_health() -> str:
    try:
        stats = get_index_stats()
        return "healthy" if stats else "unhealthy"
    except Exception as e:
        logger.error(f"Pinecone health check failed: {e}")
        return "unhealthy"

async def check_huggingface_health() -> str:
    try:
        # Simple check - try to import
        from langchain_community.llms import HuggingFaceHub
        return "healthy"
    except Exception as e:
        logger.error(f"HuggingFace health check failed: {e}")
        return "unhealthy"

@router.get("/", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    try:
        # Run health checks in parallel
        pinecone_health, hf_health = await asyncio.gather(
            check_pinecone_health(),
            check_huggingface_health()
        )

        services_health = {
            "pinecone": pinecone_health,
            "huggingface": hf_health,
            "api": "healthy"
        }

        # Overall status
        overall_status = "healthy" if all(
            status == "healthy" for status in services_health.values()
        ) else "degraded"

        return HealthCheck(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=settings.VERSION,
            services=services_health
        )

    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")

@router.get("/ready")
async def readiness_check() -> dict:
    try:
        # Check if critical services are ready
        pinecone_health = await check_pinecone_health()

        if pinecone_health != "healthy":
            raise HTTPException(status_code=503, detail="Service not ready")

        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live")
async def liveness_check() -> dict:
    # Simple liveness check - if we can respond, we're alive
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}