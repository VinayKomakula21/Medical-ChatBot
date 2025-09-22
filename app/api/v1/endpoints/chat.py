from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
import logging

from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse
# Use simple service since HF free tier doesn't support text generation models
from app.services.chat_simple import chat_service
from app.core.exceptions import LLMException

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest) -> ChatResponse:
    try:
        if request.stream:
            # For streaming, client should use WebSocket endpoint
            raise HTTPException(
                status_code=400,
                detail="For streaming responses, use the WebSocket endpoint at /ws"
            )

        response = await chat_service.generate_response(request)
        return response

    except LLMException as e:
        logger.error(f"LLM error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: str) -> List[Dict[str, Any]]:
    try:
        # Convert string to UUID
        from uuid import UUID
        conv_id = UUID(conversation_id)

        history = await chat_service.get_conversation_history(conv_id)
        return history

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history/{conversation_id}")
async def clear_conversation(conversation_id: str) -> Dict[str, str]:
    try:
        from uuid import UUID
        conv_id = UUID(conversation_id)

        success = await chat_service.clear_conversation(conv_id)
        if success:
            return {"status": "success", "message": "Conversation cleared"}
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
                    await websocket.send_json(chunk.dict())
            else:
                # Send complete response
                response = await chat_service.generate_response(request)
                await websocket.send_json(response.dict())

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        await websocket.close(code=1000)