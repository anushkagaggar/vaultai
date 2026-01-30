from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, UTC
from app.middleware.ratelimit import rate_limit
from fastapi import Depends

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, Token
from app.services.security import hash_password, verify_password
from app.services.jwt import create_access_token, create_refresh_token


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db), _: None = Depends(rate_limit)):

    result = await db.execute(
        select(User).where(User.email == user.email)
    )

    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    if len(user.password) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password too long (max 72 characters)"
        )

    new_user = User(
        email=user.email,
        password_hash=hash_password(user.password)
    )


    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    refresh_token = create_refresh_token()

    expires_at = datetime.now(UTC) + timedelta(days=7)

    new_user.refresh_token = refresh_token
    new_user.refresh_token_expires_at = expires_at

    await db.commit()

    access_token = create_access_token(
        {"user_id": new_user.id}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=Token)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db), _: None = Depends(rate_limit)):

    result = await db.execute(
        select(User).where(User.email == user.email)
    )

    db_user = result.scalar_one_or_none()

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    refresh_token = create_refresh_token()

    expires_at = datetime.now(UTC) + timedelta(days=7)

    db_user.refresh_token = refresh_token
    db_user.refresh_token_expires_at = expires_at

    await db.commit()


    access_token = create_access_token(
        {"user_id": db_user.id}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(User).where(User.refresh_token == refresh_token)
    )

    user = result.scalar_one_or_none()

    if not user or not user.refresh_token_expires_at:
        if user.refresh_token_expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=401,
                detail="Refresh token expired"
            )

    access_token = create_access_token(
        {"user_id": user.id}
    )

    return Token(access_token=access_token)
