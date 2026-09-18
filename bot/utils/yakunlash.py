"""Ro'yxatdan o'tgandan keyin yuboriladigan qo'shimcha ma'lumot.

Ikkalasini ham admin panel orqali admin kiritadi:
  - matn (qo'shimcha savollar uchun)
  - manzil (olimpiada o'tkaziladigan joy lokatsiyasi)

Ikkalasi ham ixtiyoriy — kiritilmagan bo'lsa hech narsa yuborilmaydi.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services import sozlamalar as sozlama_service

logger = logging.getLogger(__name__)


async def yakuniy_malumot(bot: Bot, session: AsyncSession, chat_id: int) -> None:
    matn = await sozlama_service.yakun_matni(session)
    if matn:
        try:
            await bot.send_message(chat_id, matn)
        except TelegramAPIError as xato:
            logger.warning("Yakuniy matn yuborilmadi (%s): %s", chat_id, xato)

    manzil = await sozlama_service.manzil(session)
    if manzil is not None:
        await manzilni_yuborish(bot, chat_id, manzil)


async def manzilni_yuborish(
    bot: Bot, chat_id: int, manzil: sozlama_service.Manzil
) -> None:
    try:
        if manzil.nomi:
            # Venue — xaritada nomi va manzili bilan chiroyli ko'rinadi
            await bot.send_venue(
                chat_id=chat_id,
                latitude=manzil.lat,
                longitude=manzil.lon,
                title=manzil.nomi,
                address=manzil.izohi or manzil.nomi,
            )
        else:
            await bot.send_location(
                chat_id=chat_id, latitude=manzil.lat, longitude=manzil.lon
            )
    except TelegramAPIError as xato:
        logger.warning("Manzil yuborilmadi (%s): %s", chat_id, xato)
