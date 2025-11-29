"""
Authentication service - handles JWT tokens and OAuth logic
Core authentication functions for creating and validating tokens
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
import logging

from app.core.config import settings
from app.models.auth import TokenPayload

logger = logging.getLogger(__name__)

# Password hashing context (for future email/password auth)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(user_id: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        user_id: User's unique ID
        email: User's email
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string

    Example:
        token = create_access_token(user_id="123", email="user@gmail.com")
        # Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Create token payload
    to_encode = {
        "sub": user_id,  # Subject (user ID)
        "email": email,
        "exp": expire,  # Expiration time
        "iat": datetime.utcnow(),  # Issued at
        "type": "access"
    }

    # Encode JWT
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    logger.info(f"Created access token for user {user_id}")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string

    Returns:
        TokenPayload if valid, None if invalid

    Example:
        payload = decode_access_token("eyJhbGciOiJIUzI1...")
        if payload:
            user_id = payload.sub
    """
    try:
        # Decode JWT
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # Validate required fields
        if payload.get("sub") is None:
            logger.warning("Token missing 'sub' claim")
            return None

        # Create TokenPayload object
        token_data = TokenPayload(
            sub=payload.get("sub"),
            email=payload.get("email"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            type=payload.get("type", "access")
        )

        return token_data

    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise

    Note: Not used for OAuth, but available for future email/password auth
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password

    Note: Not used for OAuth, but available for future email/password auth
    """
    return pwd_context.hash(password)


def create_token_response(user_id: str, email: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a complete token response with user info

    Args:
        user_id: User's unique ID
        email: User's email
        user_data: Additional user data to include

    Returns:
        Dictionary with access_token, token_type, expires_in, and user

    Example:
        response = create_token_response(
            user_id="123",
            email="user@gmail.com",
            user_data={"name": "John", "avatar_url": "..."}
        )
        # Returns: {
        #     "access_token": "eyJ...",
        #     "token_type": "bearer",
        #     "expires_in": 86400,
        #     "user": {...}
        # }
    """
    # Create access token
    access_token = create_access_token(user_id=user_id, email=email)

    # Build response
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": user_data
    }
