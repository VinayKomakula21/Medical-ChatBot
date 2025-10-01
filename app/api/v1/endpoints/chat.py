import asyncio
import json
import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.exceptions import (
    ConversationNotFoundException,
    InternalServerException,
    LLMException,
    ValidationException,
)
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse
from app.services.chat_groq import groq_chat_service as chat_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, req: Request) -> ChatResponse:
    try:
        if request.stream:
            # For streaming, client should use WebSocket endpoint
            raise ValidationException(
                "For streaming responses, use the WebSocket endpoint at /ws"
            )

        response = await chat_service.generate_response(request)
        return response

    except LLMException as e:
        logger.error(f"LLM error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise InternalServerException(str(e))

@router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: str, req: Request) -> List[Dict[str, Any]]:
    try:
        # Convert string to UUID
        conv_id = UUID(conversation_id)

        history = await chat_service.get_conversation_history(conv_id)
        return history

    except ValueError:
        raise ValidationException("Invalid conversation ID format")
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        raise InternalServerException(str(e))

@router.delete("/history/{conversation_id}")
async def clear_conversation(conversation_id: str, req: Request) -> Dict[str, str]:
    try:
        conv_id = UUID(conversation_id)

        success = await chat_service.clear_conversation(conv_id)
        if success:
            return {"status": "success", "message": "Conversation cleared"}
        else:
            raise ConversationNotFoundException(conversation_id)

    except ValueError:
        raise ValidationException("Invalid conversation ID format")
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise InternalServerException(str(e))

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
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
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Create chat request
            request = ChatRequest(**message_data)

            if request.stream:
                # Stream response chunks
                async for chunk in chat_service.generate_streaming_response(request):
                    response_data = chunk.dict()
                    # Convert UUID to string
                    if 'conversation_id' in response_data and response_data['conversation_id']:
                        response_data['conversation_id'] = str(response_data['conversation_id'])
                    await websocket.send_json(response_data)
            else:
                # Send complete response
                response = await chat_service.generate_response(request)
                response_data = response.dict()
                # Convert UUID to string
                if 'conversation_id' in response_data and response_data['conversation_id']:
                    response_data['conversation_id'] = str(response_data['conversation_id'])
                await websocket.send_json(response_data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        await websocket.close(code=1000)