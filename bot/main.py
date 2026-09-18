"""Botni ishga tushirish nuqtasi."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import load_config
from bot.db.base import create_engine, create_session_factory, init_db
from bot.db.seed import seed
from bot.handlers import admin, menu, registration
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.hisobot import hisobot_tsikli

# Windows konsoli sukut bo'yicha cp1251 — o'zbekcha harflar va emoji xato beradi
for oqim in (sys.stdout, sys.stderr):
    if hasattr(oqim, "reconfigure"):
        oqim.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()

    engine = create_engine(config.database_url)
    session_factory = create_session_factory(engine)
    await init_db(engine)
    await seed(session_factory)
    logger.info("Ma'lumotlar bazasi tayyor")

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config

    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.message.outer_middleware(ThrottlingMiddleware())

    # Tartib muhim: registratsiya FSM -> admin -> admin arizasi -> menyu
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(admin.sorov_router)
    dp.include_router(menu.router)

    hisobot_vazifasi: asyncio.Task | None = None
    try:
        me = await bot.get_me()
        logger.info(
            "Bot ishga tushdi: @%s (adminlar: %s ta)", me.username, len(config.admin_ids)
        )
        if not config.admin_ids:
            logger.warning("ADMIN_IDS bo'sh — admin panelga hech kim kira olmaydi!")

        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Boshlash / Asosiy menyu"),
                BotCommand(command="bekor", description="Amalni bekor qilish"),
            ]
        )
        await bot.delete_webhook(drop_pending_updates=True)

        # Adminlarga har kuni soat 20:00 da hisobot (Sozlamalar'dan o'chirish mumkin)
        hisobot_vazifasi = asyncio.create_task(
            hisobot_tsikli(bot, config, session_factory), name="kunlik_hisobot"
        )
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        logger.error(
            "BOT_TOKEN noto'g'ri — Telegram qabul qilmadi. "
            ".env faylni tekshiring (token @BotFather dan olinadi)."
        )
    finally:
        if hisobot_vazifasi is not None:
            hisobot_vazifasi.cancel()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
