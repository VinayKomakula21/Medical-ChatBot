"""Agentic chat endpoint — LangGraph + Groq tool-calling.

Keeps the existing /chat/message non-agentic path intact. Both endpoints can
be exercised from the frontend for A/B comparison (and for the eval suite to
measure agent-vs-RAG on the same dataset).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import observability as obs
from app.core.config import settings
from app.core.exceptions import InternalServerException
from app.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = None  # accepted but unused in v1


class AgentChatResponse(BaseModel):
    response: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    iterations: int = 0
    trace_id: Optional[str] = None
    processing_time: Optional[float] = None


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),  # accepted for future persistence; unused v1
) -> AgentChatResponse:
    """Run the LangGraph medical agent on a single user message.

    Returns the agent's final answer plus the sequence of tool calls it made
    so callers can show "this answer was built by calling X, then Y."

    Requires AGENT_ENABLED=true and GROQ_API_KEY configured. Returns a clear
    error otherwise (no silent fallback to the non-agent path — the user
    chose the agent endpoint deliberately).
    """
    if not settings.AGENT_ENABLED:
        raise InternalServerException(
            "Agentic mode is disabled. Set AGENT_ENABLED=true in your environment."
        )
    if not settings.GROQ_API_KEY:
        raise InternalServerException("GROQ_API_KEY not configured.")

    start = time.time()
    trace_id_str: Optional[str] = None
    with obs.trace(
        name="agent.chat",
        metadata={"message_preview": request.message[:120]},
    ) as trace:
        trace_id_str = getattr(trace, "id", None)
        try:
            trace.update(input={"message": request.message})
        except Exception:  # noqa: BLE001
            pass

        # Local import — keeps the agent dep off the critical-path startup time
        # when AGENT_ENABLED=false.
        from app.agent.medical_agent import run_agent

        try:
            result = await run_agent(request.message, trace=trace)
        except Exception as exc:
            logger.error("Agent run failed: %s", exc)
            raise InternalServerException(f"Agent failed: {exc}") from exc

        try:
            trace.update(output={
                "answer_length": len(result.get("answer", "")),
                "n_tool_calls": len(result.get("tool_calls") or []),
                "iterations": result.get("iterations"),
            })
        except Exception:  # noqa: BLE001
            pass

    if trace_id_str:
        response.headers["X-Trace-Id"] = trace_id_str

    return AgentChatResponse(
        response=result.get("answer", ""),
        tool_calls=result.get("tool_calls") or [],
        iterations=int(result.get("iterations") or 0),
        trace_id=trace_id_str,
        processing_time=round(time.time() - start, 3),
    )
