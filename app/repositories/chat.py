"""
Chat repository for managing conversations and messages.
Uses SQLAlchemy for persistent storage.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, User
from app.models.chat import ChatMessage, ConversationHistory
from app.repositories.base import BaseRepository


class ChatRepository(BaseRepository):
    """
    Repository for managing chat conversations.
    Uses SQLAlchemy for persistent database storage.
    """

    def __init__(self):
        super().__init__()

    async def create(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation with optional specific ID."""
        conversation = Conversation(
            id=conversation_id or str(uuid4()),  # Use provided ID or generate new
            user_id=user_id,  # Can be None for anonymous users
            title=title
        )
        db.add(conversation)
        await db.flush()

        self.logger.info(f"Created new conversation: {conversation.id}")
        return conversation

    async def get(
        self,
        db: AsyncSession,
        conversation_id: str
    ) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        db: AsyncSession,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[str] = None
    ) -> Conversation:
        """Get existing conversation or create a new one."""
        if conversation_id:
            conv_id_str = str(conversation_id)
            conversation = await self.get(db, conv_id_str)
            if conversation:
                return conversation

        # Create new conversation
        return await self.create(db, user_id=user_id)

    async def update(
        self,
        db: AsyncSession,
        conversation_id: str,
        title: Optional[str] = None
    ) -> bool:
        """Update conversation metadata."""
        conversation = await self.get(db, conversation_id)
        if not conversation:
            return False

        if title is not None:
            conversation.title = title

        await db.flush()
        self.logger.info(f"Updated conversation: {conversation_id}")
        return True

    async def delete(
        self,
        db: AsyncSession,
        conversation_id: str
    ) -> bool:
        """Delete a conversation and its messages (cascade)."""
        conversation = await self.get(db, conversation_id)
        if not conversation:
            return False

        await db.delete(conversation)
        await db.flush()

        self.logger.info(f"Deleted conversation: {conversation_id}")
        return True

    async def list(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Conversation]:
        """List conversations with pagination."""
        query = select(Conversation).order_by(Conversation.updated_at.desc())

        if user_id:
            query = query.where(Conversation.user_id == user_id)

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        user_id: Optional[str] = None
    ) -> Message:
        """Add a message to a conversation."""
        conv_id_str = str(conversation_id)

        # Get or create conversation with the SAME ID
        conversation = await self.get(db, conv_id_str)
        if not conversation:
            # Create with the provided conversation_id to maintain consistency
            conversation = await self.create(db, user_id=user_id, conversation_id=conv_id_str)

        # Create message
        message = Message(
            id=str(uuid4()),
            conversation_id=conv_id_str,  # Always use the original ID
            role=role,
            content=content
        )
        db.add(message)

        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()

        await db.flush()
        self.logger.debug(f"Added message to conversation {conv_id_str}")
        return message

    async def get_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages for a conversation."""
        conv_id_str = str(conversation_id)

        query = (
            select(Message)
            .where(Message.conversation_id == conv_id_str)
            .order_by(Message.created_at.asc())
        )

        if limit:
            # Get last N messages by ordering desc, taking N, then reversing
            query = (
                select(Message)
                .where(Message.conversation_id == conv_id_str)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(query)
            messages = list(result.scalars().all())
            return list(reversed(messages))  # Return in chronological order

        result = await db.execute(query)
        return list(result.scalars().all())

    async def clear_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> bool:
        """Clear all messages in a conversation."""
        conv_id_str = str(conversation_id)

        conversation = await self.get(db, conv_id_str)
        if not conversation:
            return False

        # Delete all messages for this conversation
        await db.execute(
            delete(Message).where(Message.conversation_id == conv_id_str)
        )

        conversation.updated_at = datetime.utcnow()
        await db.flush()

        self.logger.info(f"Cleared messages for conversation: {conversation_id}")
        return True

    async def get_conversation_context(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        max_messages: int = 10
    ) -> str:
        """Get formatted conversation context for LLM."""
        messages = await self.get_messages(db, conversation_id, limit=max_messages)

        if not messages:
            return ""

        context_parts = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg.content}")

        return "\n".join(context_parts)

    async def search_conversations(
        self,
        db: AsyncSession,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Conversation]:
        """Search conversations by message content."""
        query_lower = f"%{query.lower()}%"

        # Find conversations that have messages matching the query
        subquery = (
            select(Message.conversation_id)
            .where(func.lower(Message.content).like(query_lower))
            .distinct()
        )

        stmt = (
            select(Conversation)
            .where(Conversation.id.in_(subquery))
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )

        if user_id:
            stmt = stmt.where(Conversation.user_id == user_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_message_count(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> int:
        """Get the number of messages in a conversation."""
        conv_id_str = str(conversation_id)

        result = await db.execute(
            select(func.count(Message.id))
            .where(Message.conversation_id == conv_id_str)
        )
        return result.scalar() or 0

    # Helper method for backward compatibility with Pydantic models
    async def get_conversation_history(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> Optional[ConversationHistory]:
        """Get conversation as ConversationHistory Pydantic model."""
        conv_id_str = str(conversation_id)
        conversation = await self.get(db, conv_id_str)

        if not conversation:
            return None

        messages = await self.get_messages(db, conversation_id)

        chat_messages = [
            ChatMessage(
                role=msg.role,
                content=msg.content,
                timestamp=msg.created_at or datetime.utcnow()
            )
            for msg in messages
        ]

        return ConversationHistory(
            conversation_id=UUID(conversation.id),
            messages=chat_messages,
            created_at=conversation.created_at or datetime.utcnow(),
            updated_at=conversation.updated_at or datetime.utcnow(),
            metadata={}
        )


# Singleton instance - now requires db session to be passed to methods
chat_repository = ChatRepository()
