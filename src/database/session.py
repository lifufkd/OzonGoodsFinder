from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

from src.core.config import db_settings


engine = create_async_engine(db_settings.sqlalchemy_postgresql_url)
session_factory = async_sessionmaker(bind=engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
