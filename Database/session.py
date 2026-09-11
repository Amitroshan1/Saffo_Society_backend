"""Async PostgreSQL engine and session — replaces server/config/db.js."""

from collections.abc import AsyncGenerator

from sqlalchemy import false
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from Core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    # echo=not settings.is_production,
    echo=false(),
    pool_pre_ping=True,

)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables on startup (Alembic preferred for production migrations)."""
    from Database.base import Base
    import Models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
