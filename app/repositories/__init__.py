"""
Repository layer for data access abstraction.
Separates data persistence logic from business logic.
"""

from app.repositories.base import BaseRepository
from app.repositories.chat import ChatRepository
from app.repositories.document import DocumentRepository

__all__ = ["BaseRepository", "ChatRepository", "DocumentRepository"]