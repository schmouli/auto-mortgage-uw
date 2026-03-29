"""FastAPI dependency injection."""

from jose import JWTError
from fastapi import Depends, HTTPException, status

async def get_current_user(token: str = Depends(None)):
    """Dependency for protected endpoints."""
    # TODO: Implement JWT validation
    pass
