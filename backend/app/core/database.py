from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.core.config import settings

_engine = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))


@asynccontextmanager
async def get_session():
    async with AsyncSession(_engine) as session:
        yield session
