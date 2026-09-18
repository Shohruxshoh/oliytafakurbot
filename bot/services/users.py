"""Foydalanuvchilar bilan ishlash."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    chat_id: int,
    username: str | None,
    manba: str | None,
    familiya: str,
    ism: str,
    sharif: str,
    telefon: str,
    maktab: str,
    sinf: int,
) -> User:
    user = User(
        telegram_id=telegram_id,
        chat_id=chat_id,
        username=username,
        manba=manba,
        familiya=familiya,
        ism=ism,
        sharif=sharif,
        telefon=telefon,
        maktab=maktab,
        sinf=sinf,
    )
    session.add(user)
    await session.flush()
    return user
