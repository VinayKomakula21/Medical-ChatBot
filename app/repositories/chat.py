"""
Chat repository for managing conversations and messages.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.models.chat import ChatMessage, ConversationHistory
from app.repositories.base import BaseRepository


class ChatRepository(BaseRepository):
    """
    Repository for managing chat conversations.
    Currently uses in-memory storage, can be extended to use database.
    """

    def __init__(self):
        super().__init__()
        # In-memory storage for development
        # TODO: Replace with database storage (PostgreSQL/MongoDB)
        self._conversations: Dict[str, ConversationHistory] = {}
        self._message_history: Dict[str, List[ChatMessage]] = {}

    async def create(self, data: Dict[str, Any]) -> ConversationHistory:
        """Create a new conversation."""
        conversation_id = data.get("conversation_id") or uuid4()

        conversation = ConversationHistory(
            conversation_id=conversation_id,
            messages=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=data.get("metadata", {})
        )

        self._conversations[str(conversation_id)] = conversation
        self._message_history[str(conversation_id)] = []

        self.logger.info(f"Created new conversation: {conversation_id}")
        return conversation

    async def get(self, id: str) -> Optional[ConversationHistory]:
        """Get conversation by ID."""
        return self._conversations.get(id)

    async def update(self, id: str, data: Dict[str, Any]) -> bool:
        """Update conversation metadata."""
        if id not in self._conversations:
            return False

        conversation = self._conversations[id]
        conversation.updated_at = datetime.utcnow()

        if "metadata" in data:
            conversation.metadata = data["metadata"]

        self.logger.info(f"Updated conversation: {id}")
        return True

    async def delete(self, id: str) -> bool:
        """Delete a conversation and its messages."""
        if id not in self._conversations:
            return False

        del self._conversations[id]
        if id in self._message_history:
            del self._message_history[id]

        self.logger.info(f"Deleted conversation: {id}")
        return True

    async def list(self, skip: int = 0, limit: int = 100) -> List[ConversationHistory]:
        """List conversations with pagination."""
        conversations = list(self._conversations.values())
        # Sort by updated_at descending
        conversations.sort(key=lambda x: x.updated_at, reverse=True)
        return conversations[skip : skip + limit]

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str
    ) -> ChatMessage:
        """Add a message to a conversation."""
        conv_id_str = str(conversation_id)

        # Create conversation if it doesn't exist
        if conv_id_str not in self._conversations:
            await self.create({"conversation_id": conversation_id})

        # Create message
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )

        # Add to message history
        if conv_id_str not in self._message_history:
            self._message_history[conv_id_str] = []

        self._message_history[conv_id_str].append(message)

        # Update conversation
        conversation = self._conversations[conv_id_str]
        conversation.messages = self._message_history[conv_id_str]
        conversation.updated_at = datetime.utcnow()

        self.logger.debug(f"Added message to conversation {conversation_id}")
        return message

    async def get_messages(
        self,
        conversation_id: UUID,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get messages for a conversation."""
        conv_id_str = str(conversation_id)

        if conv_id_str not in self._message_history:
            return []

        messages = self._message_history[conv_id_str]

        if limit:
            # Return last N messages
            return messages[-limit:]

        return messages

    async def clear_messages(self, conversation_id: UUID) -> bool:
        """Clear all messages in a conversation."""
        conv_id_str = str(conversation_id)

        if conv_id_str not in self._conversations:
            return False

        self._message_history[conv_id_str] = []

        conversation = self._conversations[conv_id_str]
        conversation.messages = []
        conversation.updated_at = datetime.utcnow()

        self.logger.info(f"Cleared messages for conversation: {conversation_id}")
        return True

    async def get_conversation_context(
        self,
        conversation_id: UUID,
        max_messages: int = 10
    ) -> str:
        """Get formatted conversation context for LLM."""
        messages = await self.get_messages(conversation_id, limit=max_messages)

        if not messages:
            return ""

        context_parts = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg.content}")

        return "\n".join(context_parts)

    async def search_conversations(
        self,
        query: str,
        limit: int = 10
    ) -> List[ConversationHistory]:
        """Search conversations by content."""
        results = []
        query_lower = query.lower()

        for conv in self._conversations.values():
            # Search in messages
            for msg in conv.messages:
                if query_lower in msg.content.lower():
                    results.append(conv)
                    break

            if len(results) >= limit:
                break

        return results[:limit]


# Singleton instance
chat_repository = ChatRepository()