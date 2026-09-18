"""Adminlarga kunlik hisobot — har kuni soat 20:00 da (Toshkent vaqti).

Har bir ro'yxatdan o'tish haqida alohida xabar yuborilmaydi, o'rniga kuniga
bitta xulosa keladi. Admin panel -> Sozlamalar'da o'chirib qo'yish mumkin.
"""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Config
from bot.services import sozlamalar as sozlama_service
from bot.services import stats as stats_service
from bot.utils import vaqt
from bot.utils.notify import adminlarga

logger = logging.getLogger(__name__)

HISOBOT_SOATI = 20  # Toshkent vaqti bo'yicha


def keyingi_hisobotgacha(hozir: datetime | None = None) -> float:
    """Keyingi soat 20:00 gacha qolgan soniyalar."""
    hozir = hozir or vaqt.hozir()
    keyingi = hozir.replace(hour=HISOBOT_SOATI, minute=0, second=0, microsecond=0)
    if keyingi <= hozir:
        keyingi += timedelta(days=1)
    return (keyingi - hozir).total_seconds()


async def hisobot_matni(session: AsyncSession, sana: date | None = None) -> str:
    sana = sana or vaqt.hozir().date()
    boshlanish = vaqt.kun_boshi(sana)
    tugash = vaqt.kun_boshi(sana + timedelta(days=1))

    yangi_oquvchi = await stats_service.oquvchilar_soni(session, boshlanish, tugash)
    fanlar = await stats_service.fanlar_boyicha(session, boshlanish, tugash)
    jami_oquvchi = await stats_service.oquvchilar_soni(session)
    jami_ariza = await stats_service.arizalar_soni(session)

    qismlar = [f"📊 <b>Kunlik hisobot</b> — {sana.strftime('%d.%m.%Y')}\n"]
    if yangi_oquvchi or fanlar:
        qismlar.append(f"🆕 Bugun ro'yxatdan o'tdi: <b>{yangi_oquvchi}</b> o'quvchi")
        if fanlar:
            qismlar.append("📚 Bugungi arizalar:")
            qismlar += [f"    • {html.escape(nomi)}: {son}" for nomi, son in fanlar]
    else:
        qismlar.append("🆕 Bugun yangi ro'yxatdan o'tganlar yo'q.")
    qismlar.append(f"\n📦 Jami: <b>{jami_oquvchi}</b> o'quvchi / {jami_ariza} ariza")
    return "\n".join(qismlar)


async def hisobot_yuborish(
    bot: Bot, config: Config, session_factory: async_sessionmaker[AsyncSession]
) -> bool:
    """Bitta hisobotni barcha adminlarga yuboradi. O'chirilgan bo'lsa — False."""
    async with session_factory() as session:
        if not await sozlama_service.kunlik_hisobot_yoqilganmi(session):
            return False
        matn = await hisobot_matni(session)
        await adminlarga(bot, config, session, matn)
    return True


async def hisobot_tsikli(
    bot: Bot, config: Config, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Fon vazifasi: har kuni soat 20:00 da hisobot yuboradi. main.py ishga tushiradi."""
    while True:
        await asyncio.sleep(keyingi_hisobotgacha())
        try:
            if await hisobot_yuborish(bot, config, session_factory):
                logger.info("Kunlik hisobot yuborildi")
        except Exception:
            logger.exception("Kunlik hisobot yuborilmadi")
        # Taymer bir necha millisekund erta uyg'onsa ham bir kunda ikki marta yubormaslik uchun
        await asyncio.sleep(60)
