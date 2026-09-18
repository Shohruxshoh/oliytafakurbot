"""Adminlarga xabar yuborish."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.services import adminlar as admin_service

logger = logging.getLogger(__name__)


async def adminlarga(
    bot: Bot,
    config: Config,
    session: AsyncSession,
    matn: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    faqat_super: bool = False,
) -> None:
    """Barcha faol adminlarga (yoki faqat super adminlarga) xabar yuboradi."""
    idlar = (
        await admin_service.super_idlari(session, config)
        if faqat_super
        else await admin_service.barcha_idlar(session, config)
    )

    for admin_id in idlar:
        try:
            await bot.send_message(admin_id, matn, reply_markup=reply_markup)
        except TelegramAPIError as xato:
            logger.warning("Adminga (%s) xabar yuborilmadi: %s", admin_id, xato)
