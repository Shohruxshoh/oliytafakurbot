"""Ma'lumotlar bazasi ulanishi va sessiya fabrikasi."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Barcha modellar shu klassdan meros oladi."""


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, echo=False, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    from bot.db import models  # noqa: F401  — modellar Base.metadata ga ro'yxatdan o'tishi uchun

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
