from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, Token
from app.services.security import hash_password, verify_password
from app.services.jwt import create_access_token


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):

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

    token = create_access_token(
        {"user_id": new_user.id}
    )

    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):

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

    token = create_access_token(
        {"user_id": db_user.id}
    )

    return Token(access_token=token)
