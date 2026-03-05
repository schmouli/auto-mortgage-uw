--- routes.py ---
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.services import AuthService
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserUpdate, SessionCreate

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=UserCreate, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_async_session),
):
    service = AuthService(db)
    try:
        await service.create_user(payload)
        return payload
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "REGISTRATION_FAILED"})

@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_async_session),
):
    service = AuthService(db)
    try:
        user, session = await service.authenticate_and_create_session(email, password)
        return {
            "user_id": user.id,
            "token": session.token,
            "expires_at": session.expires_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail={"detail": str(e), "error_code": "AUTHENTICATION_FAILED"})