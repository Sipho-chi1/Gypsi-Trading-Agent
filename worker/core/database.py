"""Async SQLAlchemy session helper, shared shape with backend/app/core/database.py.
TODO: dedupe into a shared package once both services stabilise — kept
separate for now so worker/ and backend/ can be deployed as independent
Docker images without cross-importing each other."""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from core.settings import settings

_engine = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))


@asynccontextmanager
async def get_session():
    async with AsyncSession(_engine) as session:
        yield session
