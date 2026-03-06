--- routes.py ---
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Dict
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.services import AuthService
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserUpdate, SessionCreate, UserResponse
from mortgage_underwriting.modules.auth.exceptions import AuthException, UserNotFoundException

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    service = AuthService(db)
    try:
        user = await service.create_user(payload)
        return user
    except IntegrityError:
        raise HTTPException(status_code=400, detail={"detail": "Email already registered.", "error_code": "EMAIL_EXISTS"})
    except Exception:
        raise HTTPException(status_code=500, detail={"detail": "Registration failed due to internal error.", "error_code": "REGISTRATION_FAILED"})

@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, str]:
    service = AuthService(db)
    try:
        user, session = await service.authenticate_and_create_session(email, password)
        return {
            "user_id": str(user.id),
            "token": session.token,
            "expires_at": session.expires_at.isoformat()
        }
    except AuthException as e:
        raise HTTPException(status_code=401, detail={"detail": str(e), "error_code": "AUTHENTICATION_FAILED"})
    except Exception:
        raise HTTPException(status_code=500, detail={"detail": "Internal server error during authentication.", "error_code": "INTERNAL_ERROR"})