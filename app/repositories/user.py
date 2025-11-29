"""
User repository - database operations for User model
Handles CRUD operations for users
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import logging

from app.db.models import User
from app.models.auth import GoogleUserInfo

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for User database operations"""

    async def get_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """
        Get user by ID

        Args:
            db: Database session
            user_id: User's unique ID

        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """
        Get user by email address

        Args:
            db: Database session
            email: User's email

        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_google_id(self, db: AsyncSession, google_id: str) -> Optional[User]:
        """
        Get user by Google OAuth ID

        Args:
            db: Database session
            google_id: Google user ID from OAuth

        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(select(User).where(User.google_id == google_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        email: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        google_id: Optional[str] = None
    ) -> Optional[User]:
        """
        Create a new user

        Args:
            db: Database session
            email: User's email
            name: User's name (optional)
            avatar_url: User's avatar URL (optional)
            google_id: Google OAuth ID (optional)

        Returns:
            Created User object, or None if creation failed
        """
        try:
            user = User(
                email=email,
                name=name,
                avatar_url=avatar_url,
                google_id=google_id,
                is_active=True
            )

            db.add(user)
            await db.flush()  # Flush to get the ID without committing
            await db.refresh(user)

            logger.info(f"Created new user: {user.id} ({email})")
            return user

        except IntegrityError as e:
            logger.warning(f"User creation failed (duplicate email or google_id): {e}")
            await db.rollback()
            return None

    async def create_from_google(
        self,
        db: AsyncSession,
        google_user: GoogleUserInfo
    ) -> Optional[User]:
        """
        Create user from Google OAuth info

        Args:
            db: Database session
            google_user: Google user info from OAuth

        Returns:
            Created User object
        """
        return await self.create(
            db=db,
            email=google_user.email,
            name=google_user.name,
            avatar_url=google_user.picture,
            google_id=google_user.id
        )

    async def update(
        self,
        db: AsyncSession,
        user_id: str,
        **kwargs
    ) -> Optional[User]:
        """
        Update user fields

        Args:
            db: Database session
            user_id: User's ID
            **kwargs: Fields to update

        Returns:
            Updated User object, or None if not found
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return None

        # Update fields
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        await db.flush()
        await db.refresh(user)

        logger.info(f"Updated user: {user_id}")
        return user

    async def get_or_create_from_google(
        self,
        db: AsyncSession,
        google_user: GoogleUserInfo
    ) -> User:
        """
        Get existing user by Google ID or create new one

        This is the main method used during OAuth login:
        - If user exists (by google_id), return them
        - If user exists (by email) but no google_id, link the Google account
        - Otherwise, create new user

        Args:
            db: Database session
            google_user: Google user info

        Returns:
            User object (existing or newly created)
        """
        # Try to find by Google ID first
        user = await self.get_by_google_id(db, google_user.id)
        if user:
            logger.info(f"Found existing user by Google ID: {user.id}")
            # Update name/avatar in case they changed on Google
            if google_user.name and google_user.name != user.name:
                user.name = google_user.name
            if google_user.picture and google_user.picture != user.avatar_url:
                user.avatar_url = google_user.picture
            await db.flush()
            return user

        # Try to find by email (user might have signed up differently)
        user = await self.get_by_email(db, google_user.email)
        if user:
            logger.info(f"Found existing user by email, linking Google account: {user.id}")
            # Link Google account
            user.google_id = google_user.id
            if google_user.name:
                user.name = google_user.name
            if google_user.picture:
                user.avatar_url = google_user.picture
            await db.flush()
            return user

        # Create new user
        logger.info(f"Creating new user from Google OAuth: {google_user.email}")
        user = await self.create_from_google(db, google_user)
        if not user:
            raise Exception("Failed to create user")
        return user

    async def delete(self, db: AsyncSession, user_id: str) -> bool:
        """
        Delete a user (and all their data via cascade)

        Args:
            db: Database session
            user_id: User's ID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return False

        await db.delete(user)
        await db.flush()

        logger.info(f"Deleted user: {user_id}")
        return True


# Singleton instance
user_repository = UserRepository()
