"""
Authentication endpoints - OAuth login and user management
Handles Google OAuth flow and user authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth
import httpx
import logging

from app.core.config import settings
from app.db.database import get_db
from app.models.auth import Token, UserResponse, GoogleUserInfo
from app.services.auth import create_token_response
from app.repositories.user import user_repository
from app.core.security import get_current_user
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize OAuth client
oauth = OAuth()

# Only configure Google OAuth if credentials are provided
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
    logger.info("Google OAuth configured")
else:
    logger.warning("Google OAuth not configured - missing CLIENT_ID or CLIENT_SECRET")


@router.get("/google/login")
async def google_login():
    """
    Initiate Google OAuth login

    Flow:
    1. User clicks "Login with Google" button
    2. Frontend redirects to this endpoint
    3. This endpoint redirects to Google's OAuth page
    4. User approves on Google
    5. Google redirects back to /auth/google/callback

    Example:
        GET /api/v1/auth/google/login
        → Redirects to: https://accounts.google.com/o/oauth2/auth?client_id=...
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    # Build Google OAuth URL
    redirect_uri = settings.GOOGLE_REDIRECT_URI

    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Google OAuth callback

    Flow:
    1. Google redirects here with authorization code
    2. Exchange code for access token
    3. Get user info from Google
    4. Create or update user in database
    5. Generate JWT token
    6. Redirect to frontend with token

    Args:
        code: Authorization code from Google
        db: Database session

    Returns:
        Redirects to frontend with JWT token in URL
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    try:
        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )

            if token_response.status_code != 200:
                logger.error(f"Failed to get access token: {token_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to authenticate with Google"
                )

            token_data = token_response.json()
            access_token = token_data.get("access_token")

            # Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if user_info_response.status_code != 200:
                logger.error(f"Failed to get user info: {user_info_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user information from Google"
                )

            google_user_data = user_info_response.json()
            google_user = GoogleUserInfo(**google_user_data)

        # Create or get user
        user = await user_repository.get_or_create_from_google(db, google_user)
        await db.commit()

        # Create JWT token
        token_response_data = create_token_response(
            user_id=user.id,
            email=user.email,
            user_data={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "avatar_url": user.avatar_url,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
        )

        # Redirect to frontend with token
        frontend_url = settings.FRONTEND_URL
        access_token = token_response_data["access_token"]

        # Frontend should handle this URL and store the token
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?token={access_token}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's information

    Requires: Authorization header with valid JWT token

    Example:
        GET /api/v1/auth/me
        Headers: Authorization: Bearer eyJhbGc...

    Returns:
        User information (id, email, name, avatar, etc.)
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout current user

    Note: Since we're using JWT (stateless), we can't truly "invalidate" the token.
    The frontend should delete the token from storage.

    For production, you might want to:
    - Implement a token blacklist in Redis
    - Use short-lived tokens with refresh tokens
    - Track active sessions in database

    Example:
        POST /api/v1/auth/logout
        Headers: Authorization: Bearer eyJhbGc...

    Returns:
        Success message
    """
    logger.info(f"User logged out: {current_user.id}")
    return {
        "message": "Successfully logged out",
        "detail": "Please delete the token from your client storage"
    }
