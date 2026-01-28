from datetime import datetime, timedelta, UTC
from jose import jwt

from app.config import settings


def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
