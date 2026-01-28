from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.config import settings


_async_engine = None
_sync_engine = None


def get_async_engine():
    global _async_engine

    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            future=True,
        )

    return _async_engine


def get_sync_engine():
    global _sync_engine

    if _sync_engine is None:
        sync_url = settings.DATABASE_URL.replace(
            "postgresql+asyncpg",
            "postgresql+psycopg2"
        )

        _sync_engine = create_engine(
            sync_url,
            echo=False,
            future=True,
        )

    return _sync_engine


AsyncSessionLocal = sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    engine = get_async_engine()

    AsyncSessionLocal.configure(bind=engine)

    async with AsyncSessionLocal() as session:
        yield session
