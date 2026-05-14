import json
import logging
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConversationNotFoundException,
    InternalServerException,
    LLMException,
    ValidationException,
)
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.models.chat import ChatRequest, ChatResponse
from app.repositories.chat import chat_repository
from app.services.chat_groq import groq_chat_service as chat_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest, req: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    try:
        if request.stream:
            # For streaming, client should use WebSocket endpoint
            raise ValidationException("For streaming responses, use the WebSocket endpoint at /ws")

        result = await chat_service.generate_response(request, db)
        if result.trace_id:
            response.headers["X-Trace-Id"] = result.trace_id
        return result

    except LLMException as e:
        logger.error(f"LLM error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise InternalServerException(str(e))


@router.post("/stream")
async def stream_message(
    request: ChatRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events stream of the assistant response.

    Each event is a JSON-encoded StreamingChatResponse on a `data:` line, per
    the SSE spec. The stream ends with `data: [DONE]`. Clients can consume
    this with EventSource or fetch + ReadableStream.
    """

    async def event_stream():
        try:
            async for chunk in chat_service.generate_streaming_response(request, db):
                payload = (
                    chunk.model_dump(mode="json") if hasattr(chunk, "model_dump") else chunk.dict()
                )
                if payload.get("conversation_id") is not None:
                    payload["conversation_id"] = str(payload["conversation_id"])
                yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("SSE stream error: %s", exc)
            err = {"chunk": "Error generating response.", "is_final": True, "sources": []}
            yield f"data: {json.dumps(err)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering when proxied
            "Connection": "keep-alive",
        },
    )


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str, req: Request, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    try:
        # Convert string to UUID
        conv_id = UUID(conversation_id)

        history = await chat_service.get_conversation_history(db, conv_id)
        return history

    except ValueError:
        raise ValidationException("Invalid conversation ID format")
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        raise InternalServerException(str(e))


@router.delete("/history/{conversation_id}")
async def clear_conversation(
    conversation_id: str, req: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    try:
        conv_id = UUID(conversation_id)

        success = await chat_service.clear_conversation(db, conv_id)
        if success:
            return {"status": "success", "message": "Conversation cleared"}
        else:
            raise ConversationNotFoundException(conversation_id)

    except ValueError:
        raise ValidationException("Invalid conversation ID format")
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise InternalServerException(str(e))


@router.get("/conversations")
async def list_conversations(
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[dict[str, Any]]:
    """
    List all conversations for the authenticated user.
    Returns conversations sorted by most recently updated.
    """
    try:
        conversations = await chat_repository.list(
            db, user_id=current_user.id, skip=skip, limit=limit
        )

        result = []
        for conv in conversations:
            # Get message count for each conversation
            message_count = await chat_repository.get_message_count(db, UUID(conv.id))

            result.append(
                {
                    "id": conv.id,
                    "title": conv.title or "New Conversation",
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                    "message_count": message_count,
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise InternalServerException(str(e))


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    title: str | None = None,
) -> dict[str, Any]:
    """Update conversation metadata (e.g., title)."""
    try:
        UUID(conversation_id)  # validate format; raises ValueError if malformed

        # Verify conversation belongs to user
        conversation = await chat_repository.get(db, conversation_id)
        if not conversation:
            raise ConversationNotFoundException(conversation_id)

        if conversation.user_id and conversation.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        success = await chat_repository.update(db, conversation_id, title=title)
        if success:
            await db.commit()
            return {"status": "success", "message": "Conversation updated"}
        else:
            raise ConversationNotFoundException(conversation_id)

    except ValueError:
        raise ValidationException("Invalid conversation ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise InternalServerException(str(e))


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Import here to get fresh session for each message
        from app.db.database import AsyncSessionLocal

        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Create chat request
            request = ChatRequest(**message_data)

            # Create a new database session for this message
            async with AsyncSessionLocal() as db:
                try:
                    if request.stream:
                        # Stream response chunks
                        async for chunk in chat_service.generate_streaming_response(request, db):
                            response_data = chunk.dict()
                            # Convert UUID to string
                            if (
                                "conversation_id" in response_data
                                and response_data["conversation_id"]
                            ):
                                response_data["conversation_id"] = str(
                                    response_data["conversation_id"]
                                )
                            await websocket.send_json(response_data)
                    else:
                        # Send complete response
                        response = await chat_service.generate_response(request, db)
                        response_data = response.dict()
                        # Convert UUID to string
                        if "conversation_id" in response_data and response_data["conversation_id"]:
                            response_data["conversation_id"] = str(response_data["conversation_id"])
                        await websocket.send_json(response_data)

                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Error processing WebSocket message: {e}")
                    await websocket.send_json(
                        {
                            "error": str(e),
                            "conversation_id": str(request.conversation_id)
                            if request.conversation_id
                            else None,
                        }
                    )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        try:
            await websocket.close(code=1000)
        except Exception:  # noqa: BLE001 -- close is best-effort; ignore any teardown error
            pass
