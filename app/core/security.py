"""
Security dependencies for FastAPI endpoints
Provides authentication middleware for protected routes
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.database import get_db
from app.db.models import User
from app.services.auth import decode_access_token
from app.repositories.user import user_repository

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme (extracts "Authorization: Bearer <token>" header)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user

    Usage in endpoints:
        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id, "email": current_user.email}

    This function:
    1. Extracts JWT token from Authorization header
    2. Validates and decodes the token
    3. Loads the user from database
    4. Returns User object or raises HTTPException

    Args:
        credentials: Authorization credentials from header
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    # Extract token from header
    token = credentials.credentials

    # Decode and validate token
    token_data = decode_access_token(token)
    if token_data is None:
        logger.warning("Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    user = await user_repository.get_by_id(db, token_data.sub)
    if user is None:
        logger.warning(f"User not found for token: {token_data.sub}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Inactive user attempted access: {user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get current user, but doesn't fail if not authenticated

    Usage in endpoints that work with or without auth:
        @router.get("/public-or-private")
        async def flexible_route(current_user: Optional[User] = Depends(get_optional_user)):
            if current_user:
                return {"message": f"Hello {current_user.name}"}
            else:
                return {"message": "Hello guest"}

    Args:
        credentials: Optional authorization credentials
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        token_data = decode_access_token(token)
        if token_data is None:
            return None

        user = await user_repository.get_by_id(db, token_data.sub)
        if user is None or not user.is_active:
            return None

        return user

    except Exception as e:
        logger.warning(f"Error in optional auth: {e}")
        return None


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency that ensures user is active

    Usage:
        @router.get("/admin")
        async def admin_route(user: User = Depends(get_current_active_user)):
            # user is guaranteed to be active
            pass

    Args:
        current_user: Current user from get_current_user

    Returns:
        Active user

    Raises:
        HTTPException: 403 if user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
