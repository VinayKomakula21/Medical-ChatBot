"""
Authentication Pydantic models
Defines request/response schemas for authentication endpoints
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user (not used for OAuth, but available for future)"""
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    """
    User response schema - returned to frontend
    Excludes sensitive data like passwords or OAuth tokens
    """
    id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True  # Allow ORM model conversion


class UserInDB(UserBase):
    """
    User schema with all database fields
    Used internally, never sent to frontend
    """
    id: str
    google_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """
    JWT token response
    Returned after successful login/OAuth
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration
    user: UserResponse  # Include user info in response


class TokenPayload(BaseModel):
    """
    JWT token payload (what's inside the token)
    Used for encoding/decoding JWTs
    """
    sub: str  # Subject (user ID)
    email: str
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    type: str = "access"  # Token type


class GoogleUserInfo(BaseModel):
    """
    User info returned from Google OAuth API
    Matches the structure of Google's userinfo endpoint
    """
    id: str  # Google user ID
    email: EmailStr
    verified_email: bool = True  # Default to True if not provided by Google
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None  # Avatar URL
    locale: Optional[str] = None


class OAuth2CallbackRequest(BaseModel):
    """
    OAuth callback request parameters
    Contains the authorization code from Google
    """
    code: str
    state: Optional[str] = None  # CSRF protection token
