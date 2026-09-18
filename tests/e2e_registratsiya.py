"""To'liq ro'yxatdan o'tish oqimini boshidan oxirigacha sinash.

Telegram serveriga ulanmaydi — soxta sessiya ishlatiladi.
Ishga tushirish:  python tests/e2e_registratsiya.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Testlar muhitdan mustaqil bo'lishi kerak: .env yoki Docker env ni bekor qilamiz
os.environ["BOT_TOKEN"] = "123456789:SINOV-TOKENI-HAQIQIY-EMAS"
os.environ["ALOQA"] = "@test"
os.environ["ADMIN_IDS"] = "111"

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from bot.callbacks import FanCB, NavCB, SinfCB
from bot.config import load_config
from bot.db.base import create_engine, create_session_factory, init_db
from bot.db.models import Ariza, Holat, User
from bot.db.seed import seed
from bot.handlers import admin, menu, registration
from bot.middlewares.db import DbSessionMiddleware
from bot.services import sozlamalar as sozlama_service
from bot.states import Reg
from tests.mock_session import MockSession

TG_ID = 555
FOYDALANUVCHI = TgUser(id=TG_ID, is_bot=False, first_name="Alisher", username="alisher")
CHAT = Chat(id=TG_ID, type="private")

xatolar: list[str] = []
_hisoblagich = {"update": 0, "message": 0}


def tekshir(shart: bool, tavsif: str) -> None:
    print(f"  {'ok  ' if shart else 'XATO'} {tavsif}")
    if not shart:
        xatolar.append(tavsif)


def _yangi_id(kalit: str) -> int:
    _hisoblagich[kalit] += 1
    return _hisoblagich[kalit]


def matn_update(matn: str) -> Update:
    return Update(
        update_id=_yangi_id("update"),
        message=Message(
            message_id=_yangi_id("message"),
            date=datetime.now(),
            chat=CHAT,
            from_user=FOYDALANUVCHI,
            text=matn,
        ),
    )


def kontakt_update(raqam: str) -> Update:
    return Update(
        update_id=_yangi_id("update"),
        message=Message(
            message_id=_yangi_id("message"),
            date=datetime.now(),
            chat=CHAT,
            from_user=FOYDALANUVCHI,
            contact=Contact(phone_number=raqam, first_name="Alisher", user_id=TG_ID),
        ),
    )


def callback_update(data: str) -> Update:
    return Update(
        update_id=_yangi_id("update"),
        callback_query=CallbackQuery(
            id=str(_yangi_id("update")),
            from_user=FOYDALANUVCHI,
            chat_instance="test-chat-instance",
            data=data,
            message=Message(
                message_id=_yangi_id("message"),
                date=datetime.now(),
                chat=CHAT,
                text="savol",
            ),
        ),
    )


async def main() -> None:
    config = load_config()

    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)
    await init_db(engine)
    await seed(session_factory)

    # Admin oldindan yakuniy matn va manzilni kiritib qo'ygan
    async with session_factory() as s:
        await sozlama_service.yakun_matnini_saqlash(
            s, "❓ Savollar bo'lsa: @oliytafakkur_admin"
        )
        await sozlama_service.manzil_saqlash(
            s, 41.311081, 69.240562, "Oliy Tafakkur markazi", "Toshkent, Chilonzor"
        )
        await s.commit()

    session_obj = MockSession()
    bot = Bot(
        config.bot_token,
        session=session_obj,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp["config"] = config
    dp.update.middleware(DbSessionMiddleware(session_factory))
    # Throttling qo'shilmaydi: test update'larni ketma-ket, tez yuboradi
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(menu.router)

    kalit = StorageKey(bot_id=bot.id, chat_id=TG_ID, user_id=TG_ID)

    async def holat() -> str | None:
        return await storage.get_state(kalit)

    async def yubor(update: Update) -> None:
        session_obj.tozalash()
        await dp.feed_update(bot, update)

    print("\n[1] /start — registratsiya boshlandi")
    await yubor(matn_update("/start"))
    tekshir(await holat() == Reg.familiya.state, f"holat: {await holat()}")
    tekshir("Familiya" in session_obj.oxirgi_matn(), "familiya so'raldi")

    print("\n[2] Noto'g'ri familiya rad etiladi")
    await yubor(matn_update("Ali123"))
    tekshir(await holat() == Reg.familiya.state, "holat o'zgarmadi")
    tekshir("❌" in session_obj.oxirgi_matn(), "xato xabari chiqdi")

    print("\n[3] F.I.Sh. kiritish")
    await yubor(matn_update("aliyev"))
    tekshir(await holat() == Reg.ism.state, "ism qadamiga o'tdi")
    await yubor(matn_update("alisher"))
    tekshir(await holat() == Reg.sharif.state, "sharif qadamiga o'tdi")

    print("\n[4] Orqaga qaytish ishlaydi")
    await yubor(matn_update("⬅️ Orqaga"))
    tekshir(await holat() == Reg.ism.state, "ism qadamiga qaytdi")
    await yubor(matn_update("Alisher"))
    await yubor(matn_update("akmalovich"))
    tekshir(await holat() == Reg.telefon.state, "telefon qadamiga o'tdi")

    print("\n[5] Telefon — kontakt orqali")
    await yubor(matn_update("noto'g'ri raqam"))
    tekshir(await holat() == Reg.telefon.state, "noto'g'ri raqam qabul qilinmadi")
    await yubor(kontakt_update("+998901234567"))
    tekshir(await holat() == Reg.maktab.state, "maktab qadamiga o'tdi")

    print("\n[6] Maktab va sinf")
    await yubor(matn_update("Chilonzor tumani, 45-maktab"))
    tekshir(await holat() == Reg.sinf.state, "sinf qadamiga o'tdi")
    await yubor(callback_update(SinfCB(sinf=5).pack()))
    tekshir(await holat() == Reg.fanlar.state, "fanlar qadamiga o'tdi")

    print("\n[7] Fan tanlash (bir nechta)")
    async with session_factory() as s:
        from bot.services.arizalar import faol_fanlar

        fanlar = await faol_fanlar(s)
    mat, ing = fanlar[0], fanlar[1]

    await yubor(callback_update(FanCB(action="done").pack()))
    tekshir(await holat() == Reg.fanlar.state, "fansiz davom etib bo'lmaydi")

    await yubor(callback_update(FanCB(action="toggle", fan_id=mat.id).pack()))
    await yubor(callback_update(FanCB(action="toggle", fan_id=ing.id).pack()))
    data = await storage.get_data(kalit)
    tekshir(sorted(data.get("fan_ids", [])) == sorted([mat.id, ing.id]), "2 ta fan belgilandi")

    await yubor(callback_update(FanCB(action="toggle", fan_id=ing.id).pack()))
    data = await storage.get_data(kalit)
    tekshir(data.get("fan_ids") == [mat.id], "qayta bosilganda belgi olinadi")

    await yubor(callback_update(FanCB(action="done").pack()))
    tekshir(await holat() == Reg.tasdiq.state, "tasdiqlash ekraniga o'tdi")
    xulosa = session_obj.oxirgi_matn()
    tekshir("Aliyev Alisher Akmalovich" in xulosa, "xulosada F.I.Sh. bor")
    tekshir("+998901234567" in xulosa, "xulosada telefon bor")
    tekshir("5-sinf" in xulosa, "xulosada sinf bor")
    tekshir(mat.nomi in xulosa and ing.nomi not in xulosa, "xulosada faqat tanlangan fan")

    print("\n[8] Tahrirlash: sinfni o'zgartirish")
    await yubor(callback_update(NavCB(action="edit").pack()))
    from bot.callbacks import TahrirCB

    await yubor(callback_update(TahrirCB(maydon="sinf").pack()))
    tekshir(await holat() == Reg.sinf.state, "sinf qadamiga qaytdi")
    await yubor(callback_update(SinfCB(sinf=7).pack()))
    tekshir(await holat() == Reg.tasdiq.state, "tasdiqlash ekraniga qaytdi")
    tekshir("7-sinf" in session_obj.oxirgi_matn(), "yangi sinf xulosada")

    print("\n[9] Tasdiqlash — bazaga yozish")
    await yubor(callback_update(NavCB(action="confirm").pack()))
    tekshir(await holat() is None, "FSM tozalandi")

    async with session_factory() as s:
        user = await s.scalar(select(User).where(User.telegram_id == TG_ID))
        tekshir(user is not None, "foydalanuvchi bazada")
        assert user is not None
        tekshir(user.fish == "Aliyev Alisher Akmalovich", f"F.I.Sh.: {user.fish}")
        tekshir(user.telefon == "+998901234567", f"telefon: {user.telefon}")
        tekshir(user.sinf == 7, f"sinf: {user.sinf}")
        tekshir(user.maktab == "Chilonzor tumani, 45-maktab", "maktab saqlandi")

        arizalar = list(
            (await s.scalars(select(Ariza).where(Ariza.user_id == user.id))).all()
        )
        tekshir(len(arizalar) == 1, f"1 ta ariza yaratildi ({len(arizalar)})")
        tekshir(
            all(a.holat == Holat.YANGI for a in arizalar), "arizalar 'yangi' holatida"
        )
        raqamlar = [a.ariza_raqami for a in arizalar]
        tekshir(all(r and r.startswith("OT") for r in raqamlar), f"raqamlar: {raqamlar}")

    yuborilgan = session_obj.matnlar()
    tekshir(
        any("Tabriklaymiz" in m for m in yuborilgan), "foydalanuvchiga tabrik yuborildi"
    )
    tekshir(
        any("Yangi ro'yxatdan o'tish" in m for m in yuborilgan),
        "adminga xabar yuborildi",
    )

    yakun = next((m for m in yuborilgan if "Tabriklaymiz" in m), "")
    tekshir("Aliyev Alisher Akmalovich" in yakun, "yakuniy xabarda F.I.Sh.")
    tekshir("+998901234567" in yakun, "yakuniy xabarda telefon")
    tekshir("Chilonzor tumani, 45-maktab" in yakun, "yakuniy xabarda maktab")
    tekshir("7-sinf" in yakun, "yakuniy xabarda sinf")
    tekshir(mat.nomi in yakun and "OT" in yakun, "yakuniy xabarda fan va ariza raqami")

    tekshir(
        any("@oliytafakkur_admin" in m for m in yuborilgan),
        "admin kiritgan qo'shimcha matn yuborildi",
    )
    tekshir("SendVenue" in session_obj.metodlar(), "admin kiritgan manzil yuborildi")

    print("\n[10] Takroriy /start — asosiy menyu")
    await yubor(matn_update("/start"))
    tekshir("menyu" in session_obj.oxirgi_matn().lower(), "asosiy menyu ko'rsatildi")

    print("\n[11] Mening arizalarim")
    await yubor(matn_update("📋 Mening arizalarim"))
    matn = session_obj.oxirgi_matn()
    tekshir("arizalaringiz" in matn.lower(), "arizalar ro'yxati chiqdi")
    tekshir(mat.nomi in matn, "tanlangan fan ro'yxatda")

    print("\n[12] Yana fan qo'shish")
    await yubor(matn_update("➕ Yana fan qo'shish"))
    await yubor(callback_update(FanCB(action="toggle", fan_id=ing.id).pack()))
    await yubor(callback_update(FanCB(action="done").pack()))
    async with session_factory() as s:
        user = await s.scalar(select(User).where(User.telegram_id == TG_ID))
        assert user is not None
        arizalar = list(
            (await s.scalars(select(Ariza).where(Ariza.user_id == user.id))).all()
        )
        tekshir(len(arizalar) == 2, f"2-fan qo'shildi ({len(arizalar)})")

    # Regressiya: ilgari FSM holatida menyu tugmalari JIM ishlamas edi
    # (handlerlarda StateFilter(None) turgani uchun) — bot javob bermay qolardi.
    print("\n[13] FSM holatida ham menyu tugmalari ishlaydi")
    await yubor(matn_update("✏️ Ma'lumotlarimni tahrirlash"))
    tekshir(await holat() is not None, f"tahrirlash holatiga o'tdi: {await holat()}")

    await yubor(matn_update("📞 Aloqa"))
    tekshir("Aloqa" in session_obj.oxirgi_matn(), "holat ichidan «Aloqa» ishladi")
    tekshir(await holat() is None, "menyu tugmasi holatni tozaladi")

    await yubor(matn_update("📋 Mening arizalarim"))
    tekshir("arizalaringiz" in session_obj.oxirgi_matn().lower(), "«Arizalarim» ishladi")

    print("\n[14] Hech qanday xabar javobsiz qolmaydi")
    await yubor(matn_update("salom, qanday qatnashaman?"))
    tekshir(
        "menyudan tanlang" in session_obj.oxirgi_matn().lower(),
        "tushunarsiz xabarga yo'riqnoma berildi",
    )

    await yubor(matn_update("✏️ Ma'lumotlarimni tahrirlash"))
    await yubor(matn_update("tasodifiy matn"))
    tekshir(
        "tugmalardan birini tanlang" in session_obj.oxirgi_matn(),
        "holat ichida ham javob keladi",
    )
    await yubor(matn_update("/bekor"))
    tekshir(await holat() is None, "/bekor holatni tozaladi")

    await bot.session.close()
    await engine.dispose()

    print("\n" + "=" * 55)
    if xatolar:
        print(f"XATOLAR: {len(xatolar)}")
        for x in xatolar:
            print("  -", x)
        sys.exit(1)
    print("TO'LIQ OQIM ISHLAYAPTI ✅")


if __name__ == "__main__":
    asyncio.run(main())
