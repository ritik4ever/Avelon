"""Async SQLAlchemy database engine and session management."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.migrations.runner import run_migrations_in_connection

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ensure_schema() -> None:
    """Create missing tables and additive columns for forward-compatible startup."""
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations_in_connection)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE benchmark_runs ADD COLUMN IF NOT EXISTS category_performance JSONB")
        )
        await conn.execute(
            text("ALTER TABLE benchmark_runs ADD COLUMN IF NOT EXISTS benchmark_summary TEXT")
        )
