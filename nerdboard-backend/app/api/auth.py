"""
Authentication Middleware

Simple bearer token authentication for MVP demo.
Placeholder for future OAuth integration.
"""
import logging
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

# Demo token for MVP (in production, use proper JWT/OAuth)
DEMO_TOKEN = "demo_token_12345"

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json"
}


def is_public_endpoint(path: str) -> bool:
    """Check if endpoint is public"""
    return path in PUBLIC_ENDPOINTS or path.startswith("/api/docs")


async def verify_token(credentials: Optional[HTTPAuthorizationCredentials]) -> bool:
    """
    Verify bearer token.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        True if valid, raises HTTPException otherwise
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_001",
                    "message": "Authorization header missing",
                    "details": "Please provide a valid bearer token"
                }
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    # MVP: Simple token comparison
    # In production: Decode and validate JWT
    if token != DEMO_TOKEN:
        logger.warning(f"Invalid token attempt: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_002",
                    "message": "Invalid or expired token",
                    "details": "The provided token is not valid"
                }
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    return True


async def get_current_user(credentials: HTTPAuthorizationCredentials) -> dict:
    """
    Get current user from token.

    Placeholder for future user context extraction from JWT.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        User context dictionary
    """
    await verify_token(credentials)

    # In production, would decode JWT and extract user info
    return {
        "user_id": "demo_user",
        "username": "demo",
        "role": "admin"
    }


class AuthenticationMiddleware:
    """
    Middleware to enforce authentication on protected endpoints.
    """

    async def __call__(self, request: Request, call_next):
        """Process request with authentication check"""

        # Skip authentication for public endpoints
        if is_public_endpoint(request.url.path):
            return await call_next(request)

        # Extract authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "AUTH_001",
                        "message": "Unauthorized",
                        "details": "Authorization header required"
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Verify bearer token format
        if not auth_header.startswith("Bearer "):
            return HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "AUTH_003",
                        "message": "Invalid authorization format",
                        "details": "Use 'Bearer <token>' format"
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Extract and verify token
        token = auth_header.replace("Bearer ", "")

        if token != DEMO_TOKEN:
            logger.warning(f"Authentication failed for path: {request.url.path}")
            return HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "AUTH_002",
                        "message": "Invalid token",
                        "details": "The provided token is not valid"
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Add user context to request state (for future use)
        request.state.user = {
            "user_id": "demo_user",
            "username": "demo",
            "role": "admin"
        }

        # Continue request processing
        return await call_next(request)
