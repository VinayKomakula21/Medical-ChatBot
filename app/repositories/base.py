"""
Base repository class with common functionality.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    """
    Abstract base repository class.
    Provides common interface for all repositories.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Any:
        """Create a new entity."""
        pass

    @abstractmethod
    async def get(self, id: str) -> Optional[Any]:
        """Get entity by ID."""
        pass

    @abstractmethod
    async def update(self, id: str, data: Dict[str, Any]) -> bool:
        """Update entity by ID."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete entity by ID."""
        pass

    @abstractmethod
    async def list(self, skip: int = 0, limit: int = 100) -> List[Any]:
        """List entities with pagination."""
        pass

    async def exists(self, id: str) -> bool:
        """Check if entity exists."""
        entity = await self.get(id)
        return entity is not None

    async def count(self) -> int:
        """Get total count of entities."""
        # Default implementation - override for optimization
        items = await self.list(skip=0, limit=999999)
        return len(items)