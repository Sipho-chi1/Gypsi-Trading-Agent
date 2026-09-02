from contextlib import asynccontextmanager
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.core.config import settings

_db_url = make_url(settings.DATABASE_URL)
if _db_url.drivername in ("postgresql", "postgres"):
    _db_url = _db_url.set(drivername="postgresql+asyncpg")

_engine = create_async_engine(_db_url)


@asynccontextmanager
async def get_session():
    async with AsyncSession(_engine) as session:
        yield session
