"""Admin panel oqimini sinash.

Qamrov: panel va rollar, davr statistikasi (kunlik/haftalik/oylik),
har bir davr uchun Excel, avtomatik qabul, rad etish / qayta qabul, qidiruv,
broadcast, adminlarni boshqarish (ariza -> super admin tasdig'i),
sozlamalar va kunlik hisobot.

Ishga tushirish:  python tests/e2e_admin.py
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
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from bot.callbacks import AdmCB
from bot.config import load_config
from bot.db.base import create_engine, create_session_factory, init_db
from bot.db.models import Admin, AdminHolat, Ariza, Holat
from bot.db.seed import seed
from bot.handlers import admin, menu, registration
from bot.middlewares.db import DbSessionMiddleware
from bot.services import adminlar as admin_service
from bot.services import arizalar as ariza_service
from bot.services import hisobot
from bot.services import sozlamalar as sozlama_service
from bot.services import users as user_service
from tests.mock_session import MockSession

SUPER_ID = 111  # .env dagi doimiy super admin
YANGI_ADMIN_ID = 777  # ariza yuborib admin bo'ladi
BEGONA_ID = 999  # hech qachon admin bo'lmaydi

xatolar: list[str] = []
_hisob = {"n": 0}


def tekshir(shart: bool, tavsif: str) -> None:
    print(f"  {'ok  ' if shart else 'XATO'} {tavsif}")
    if not shart:
        xatolar.append(tavsif)


def _n() -> int:
    _hisob["n"] += 1
    return _hisob["n"]


def matn_update(matn: str, user_id: int = SUPER_ID) -> Update:
    return Update(
        update_id=_n(),
        message=Message(
            message_id=_n(),
            date=datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=TgUser(id=user_id, is_bot=False, first_name="Admin"),
            text=matn,
        ),
    )


def callback_update(data: str, user_id: int = SUPER_ID) -> Update:
    return Update(
        update_id=_n(),
        callback_query=CallbackQuery(
            id=str(_n()),
            from_user=TgUser(
                id=user_id, is_bot=False, first_name="Admin", username="adminuser"
            ),
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=_n(),
                date=datetime.now(),
                chat=Chat(id=user_id, type="private"),
                text="admin xabari",
            ),
        ),
    )


async def main() -> None:
    config = load_config()
    admin_service.keshni_tozalash()

    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)
    await init_db(engine)
    await seed(session_factory)

    # Ikkita o'quvchi tayyorlab qo'yamiz
    async with session_factory() as s:
        fanlar = await ariza_service.faol_fanlar(s)
        oquvchilar = []
        for nomer, (familiya, sinf) in enumerate(
            [("Aliyev", 5), ("Karimova", 7)], start=1
        ):
            user = await user_service.create_user(
                s,
                telegram_id=1000 + nomer,
                chat_id=1000 + nomer,
                username=f"user{nomer}",
                manba=None,
                familiya=familiya,
                ism="Test",
                sharif="Testovich",
                telefon=f"+99890123456{nomer}",
                maktab=f"{nomer}0-maktab",
                sinf=sinf,
            )
            await ariza_service.ariza_yaratish(s, user, [fanlar[0].id, fanlar[1].id])
            oquvchilar.append(user)
        await s.commit()
        oquvchi1_id, oquvchi2_id = oquvchilar[0].id, oquvchilar[1].id

    session_obj = MockSession()
    bot = Bot(
        config.bot_token,
        session=session_obj,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(admin.sorov_router)
    dp.include_router(menu.router)

    async def yubor(update: Update) -> None:
        session_obj.tozalash()
        await dp.feed_update(bot, update)

    # ---------------------------------------------------------------- panel
    print("\n[1] Super admin paneli")
    await yubor(matn_update("/admin"))
    tekshir("Admin panel" in session_obj.oxirgi_matn(), "panel ochildi")
    tekshir("Super admin" in session_obj.oxirgi_matn(), "rol ko'rsatildi")
    markup = session_obj.oxirgi_markup()
    tekshir(markup is not None and len(markup.inline_keyboard) == 5, "super panelda 5 qator")

    # ---------------------------------------------------------------- statistika
    print("\n[2] Umumiy statistika — davrlar bo'yicha")
    await yubor(callback_update(AdmCB(action="stat").pack()))
    stat = session_obj.oxirgi_matn()
    tekshir("Ro'yxatdan o'tganlar" in stat, "statistika chiqdi")
    tekshir("📅 Bugun: <b>2</b> o'quvchi / 4 ariza" in stat, "bugungi sanoq")
    tekshir("📆 Shu hafta: <b>2</b> o'quvchi / 4 ariza" in stat, "haftalik sanoq")
    tekshir("🗓 Shu oy: <b>2</b> o'quvchi / 4 ariza" in stat, "oylik sanoq")
    tekshir("📦 Jami: <b>2</b> o'quvchi / 4 ariza" in stat, "umumiy sanoq")
    tekshir(fanlar[0].nomi in stat, "fanlar kesimi bor")
    tekshir("5-sinf: 1" in stat and "7-sinf: 1" in stat, "sinflar kesimi bor")

    print("\n[3] Kunlik / haftalik / oylik jadvallar")
    await yubor(callback_update(AdmCB(action="stat_kun").pack()))
    kunlik = session_obj.oxirgi_matn()
    tekshir("Kunlik statistika" in kunlik, "kunlik jadval chiqdi")
    tekshir("<pre>" in kunlik and "Jami: <b>2</b>" in kunlik, "jadval va yig'indi")
    tekshir("▇" in kunlik, "diagramma chizildi")

    await yubor(callback_update(AdmCB(action="stat_hafta").pack()))
    haftalik = session_obj.oxirgi_matn()
    tekshir("Haftalik statistika" in haftalik, "haftalik jadval chiqdi")
    tekshir("Jami: <b>2</b>" in haftalik, "haftalik yig'indi")

    await yubor(callback_update(AdmCB(action="stat_oy").pack()))
    oylik = session_obj.oxirgi_matn()
    tekshir("Oylik statistika" in oylik, "oylik jadval chiqdi")
    tekshir("Jami: <b>2</b>" in oylik, "oylik yig'indi")

    # ---------------------------------------------------------------- eksport
    print("\n[4] Har bir davr uchun Excel")
    await yubor(callback_update(AdmCB(action="eksport").pack()))
    tekshir("Qaysi davr" in session_obj.oxirgi_matn(), "eksport menyusi ochildi")
    tekshir(len(session_obj.oxirgi_markup().inline_keyboard) == 3, "4 ta davr + orqaga")

    for action, nomi in (
        ("eks_kun", "bugungi"),
        ("eks_hafta", "haftalik"),
        ("eks_oy", "oylik"),
        ("eks_hammasi", "to'liq"),
    ):
        await yubor(callback_update(AdmCB(action=action).pack()))
        hujjatlar = [nom for nom in session_obj.metodlar() if nom == "SendDocument"]
        tekshir(len(hujjatlar) == 1, f"{nomi} Excel yuborildi")

    # ---------------------------------------------------------------- arizalar
    print("\n[5] Oxirgi arizalar — avtomatik qabul qilingan")
    async with session_factory() as s:
        holatlar = list((await s.scalars(select(Ariza.holat))).all())
        tekshir(
            len(holatlar) == 4 and all(h == Holat.TASDIQLANGAN for h in holatlar),
            "4 ta ariza admin tasdig'isiz qabul qilingan",
        )

    await yubor(callback_update(AdmCB(action="yangi").pack()))
    tekshir(
        any("Oxirgi 2 ta o'quvchi" in m for m in session_obj.matnlar()),
        "oxirgi arizalar ro'yxati ochildi",
    )
    kartalar = [
        metod
        for nom, metod in session_obj.calls
        if nom == "SendMessage" and "Arizalar:" in (metod.text or "")
    ]
    tekshir(len(kartalar) == 2, f"2 ta o'quvchi kartasi ({len(kartalar)})")
    tugmalar = [t.text for k in kartalar for qator in k.reply_markup.inline_keyboard for t in qator]
    tekshir(
        tugmalar.count("❌ Rad etish") == 2 and not any("Qayta qabul" in x for x in tugmalar),
        "kartada faqat «Rad etish» (hamma ariza allaqachon qabul qilingan)",
    )

    # Eski xabardagi «Tasdiqlash» tugmasi bosilsa — hech narsa o'zgarmaydi, o'quvchiga xabar ketmaydi
    await yubor(callback_update(AdmCB(action="tasdiq_user", value=oquvchi1_id).pack()))
    tekshir(session_obj.matnlar() == [], "qabul qilingan o'quvchiga qayta xabar yuborilmadi")

    print("\n[6] Rad etish (sabab bilan) — statistika va Excel'dan chiqadi")
    await yubor(callback_update(AdmCB(action="rad_user", value=oquvchi2_id).pack()))
    tekshir("sabab" in session_obj.oxirgi_matn().lower(), "sabab so'raldi")
    await yubor(matn_update("Maktab nomi noto'g'ri ko'rsatilgan"))
    tekshir("2 ta ariza rad etildi" in session_obj.matnlar()[0], "adminga natija aytildi")
    tekshir(
        any("rad etildi" in m and "Sabab" in m for m in session_obj.matnlar()),
        "o'quvchiga sabab bilan xabar ketdi",
    )
    async with session_factory() as s:
        arizalar = list(
            (await s.scalars(select(Ariza).where(Ariza.user_id == oquvchi2_id))).all()
        )
        tekshir(all(a.holat == Holat.RAD_ETILGAN for a in arizalar), "arizalar rad etildi")
        tekshir(
            all(a.admin_izohi == "Maktab nomi noto'g'ri ko'rsatilgan" for a in arizalar),
            "rad etish sababi saqlandi",
        )

    await yubor(callback_update(AdmCB(action="stat").pack()))
    tekshir(
        "📦 Jami: <b>1</b> o'quvchi / 2 ariza" in session_obj.oxirgi_matn(),
        "statistikada rad etilgan sanalmadi (2 -> 1 o'quvchi)",
    )
    await yubor(callback_update(AdmCB(action="eks_hammasi").pack()))
    hujjat = next(m for nom, m in session_obj.calls if nom == "SendDocument")
    tekshir("<b>2</b> ta ariza" in (hujjat.caption or ""), "Excel'ga faqat 2 ta ariza tushdi")

    print("\n[6.1] Xato bilan rad etilganni qayta qabul qilish")
    await yubor(callback_update(AdmCB(action="tasdiq_user", value=oquvchi2_id).pack()))
    async with session_factory() as s:
        arizalar = list(
            (await s.scalars(select(Ariza).where(Ariza.user_id == oquvchi2_id))).all()
        )
        tekshir(
            all(a.holat == Holat.TASDIQLANGAN and a.admin_izohi is None for a in arizalar),
            "arizalar qayta qabul qilindi, rad sababi tozalandi",
        )
    tekshir(
        any("qabul qilindi" in m.lower() for m in session_obj.matnlar()),
        "o'quvchiga «qabul qilindi» xabari ketdi",
    )
    tekshir(
        any("Qayta qabul qilindi" in m for m in session_obj.matnlar()),
        "admin kartasi yangilandi",
    )
    await yubor(callback_update(AdmCB(action="stat").pack()))
    tekshir(
        "📦 Jami: <b>2</b> o'quvchi / 4 ariza" in session_obj.oxirgi_matn(),
        "statistika qayta tiklandi",
    )

    print("\n[7] Qidiruv va /bekor")
    await yubor(callback_update(AdmCB(action="qidiruv").pack()))
    await yubor(matn_update("Aliyev"))
    tekshir("Aliyev" in session_obj.oxirgi_matn(), "qidiruv natija berdi")

    await yubor(callback_update(AdmCB(action="rad_user", value=oquvchi1_id).pack()))
    await yubor(matn_update("/bekor"))
    tekshir("Bekor qilindi" in session_obj.oxirgi_matn(), "/bekor ishladi")
    async with session_factory() as s:
        holatlar = list(
            (await s.scalars(select(Ariza.holat).where(Ariza.user_id == oquvchi1_id))).all()
        )
        tekshir(
            all(h == Holat.TASDIQLANGAN for h in holatlar), "/bekor sabab sifatida yozilmadi"
        )

    # ---------------------------------------------------------------- adminlar
    print("\n[8] Admin bo'lmagan odam ariza yuboradi")
    await yubor(matn_update("/admin", user_id=YANGI_ADMIN_ID))
    tekshir("admin huquqi yo'q" in session_obj.oxirgi_matn(), "ariza taklif qilindi")

    await yubor(callback_update(AdmCB(action="sorov").pack(), user_id=YANGI_ADMIN_ID))
    tekshir(
        any("Ariza yuborildi" in m for m in session_obj.matnlar()),
        "arizachiga tasdiq berildi",
    )
    tekshir(
        any("Admin bo'lish uchun ariza" in m for m in session_obj.matnlar()),
        "super adminga xabar bordi",
    )

    async with session_factory() as s:
        sorov = await s.scalar(select(Admin).where(Admin.telegram_id == YANGI_ADMIN_ID))
        tekshir(
            sorov is not None and sorov.holat == AdminHolat.KUTILMOQDA,
            "ariza bazada, tasdiq kutmoqda",
        )
        sorov_id = sorov.id

    await yubor(matn_update("/admin", user_id=YANGI_ADMIN_ID))
    tekshir("kuting" in session_obj.oxirgi_matn().lower(), "takroran — kutish xabari")

    print("\n[9] Super admin tasdiqlaydi")
    await yubor(callback_update(AdmCB(action="admin_tasdiq", value=sorov_id).pack()))
    tekshir(
        any("admin etib tayinlandingiz" in m.lower() for m in session_obj.matnlar()),
        "yangi adminga xabar yuborildi",
    )
    async with session_factory() as s:
        tekshir(
            await admin_service.admin_mi(s, config, YANGI_ADMIN_ID), "endi admin hisoblanadi"
        )
        tekshir(
            not await admin_service.super_mi(s, config, YANGI_ADMIN_ID),
            "lekin super admin emas",
        )

    print("\n[10] Yangi adminning huquqlari cheklangan")
    await yubor(matn_update("/admin", user_id=YANGI_ADMIN_ID))
    tekshir("Admin panel" in session_obj.oxirgi_matn(), "panelga kira oladi")
    markup = session_obj.oxirgi_markup()
    tekshir(markup is not None and len(markup.inline_keyboard) == 3, "oddiy panelda 3 qator")
    tugmalar = [t.text for qator in markup.inline_keyboard for t in qator]
    tekshir(
        not any("Xabar yuborish" in x or "Adminlar" in x for x in tugmalar),
        "broadcast va adminlar tugmalari yo'q",
    )

    await yubor(callback_update(AdmCB(action="broadcast").pack(), user_id=YANGI_ADMIN_ID))
    tekshir(session_obj.matnlar() == [], "broadcast oddiy adminga ishlamaydi")

    await yubor(callback_update(AdmCB(action="adminlar").pack(), user_id=YANGI_ADMIN_ID))
    tekshir(session_obj.matnlar() == [], "adminlar ro'yxati oddiy adminga ochilmaydi")

    await yubor(callback_update(AdmCB(action="stat").pack(), user_id=YANGI_ADMIN_ID))
    tekshir("Ro'yxatdan o'tganlar" in session_obj.oxirgi_matn(), "statistikani ko'ra oladi")

    print("\n[11] Adminlarni boshqarish")
    await yubor(callback_update(AdmCB(action="adminlar").pack()))
    royxat = session_obj.oxirgi_matn()
    tekshir("Adminlar" in royxat, "adminlar ro'yxati ochildi")
    tekshir(str(YANGI_ADMIN_ID) in royxat, "yangi admin ro'yxatda")

    await yubor(callback_update(AdmCB(action="admin_super", value=sorov_id).pack()))
    async with session_factory() as s:
        tekshir(
            await admin_service.super_mi(s, config, YANGI_ADMIN_ID), "super rolga ko'tarildi"
        )

    await yubor(callback_update(AdmCB(action="admin_qosh").pack()))
    tekshir("Telegram ID" in session_obj.oxirgi_matn(), "ID so'raldi")
    await yubor(matn_update("abc"))
    tekshir("raqam bo'lishi kerak" in session_obj.oxirgi_matn(), "noto'g'ri ID rad etildi")
    await yubor(matn_update("888 Qo'lda Qo'shilgan"))
    async with session_factory() as s:
        qoshilgan = await s.scalar(select(Admin).where(Admin.telegram_id == 888))
        tekshir(
            qoshilgan is not None and qoshilgan.holat == AdminHolat.TASDIQLANGAN,
            "qo'lda admin qo'shildi",
        )

    await yubor(callback_update(AdmCB(action="admin_ochir", value=sorov_id).pack()))
    async with session_factory() as s:
        tekshir(
            not await admin_service.admin_mi(s, config, YANGI_ADMIN_ID),
            "adminlikdan olindi",
        )

    print("\n[12] Sozlamalar: yakuniy matn va manzil")
    await yubor(callback_update(AdmCB(action="sozlamalar").pack()))
    tekshir("Sozlamalar" in session_obj.oxirgi_matn(), "sozlamalar bo'limi ochildi")

    await yubor(callback_update(AdmCB(action="yakun_matn").pack()))
    tekshir("Yakuniy matn" in session_obj.oxirgi_matn(), "matn tahriri ochildi")
    await yubor(matn_update("Savollar bo'lsa +998901112233 ga qo'ng'iroq qiling"))
    async with session_factory() as s:
        saqlangan = await sozlama_service.yakun_matni(s)
        tekshir("998901112233" in saqlangan, "yakuniy matn saqlandi")

    await yubor(callback_update(AdmCB(action="manzil").pack()))
    tekshir("Manzil" in session_obj.oxirgi_matn(), "manzil tahriri ochildi")

    await yubor(matn_update("bu koordinata emas"))
    tekshir(
        "Koordinata topilmadi" in session_obj.oxirgi_matn(),
        "noto'g'ri koordinata rad etildi",
    )

    await yubor(matn_update("41.311081, 69.240562 | Oliy Tafakkur markazi"))
    async with session_factory() as s:
        manzil = await sozlama_service.manzil(s)
        tekshir(
            manzil is not None
            and round(manzil.lat, 4) == 41.3111
            and manzil.nomi == "Oliy Tafakkur markazi",
            f"manzil saqlandi: {manzil}",
        )
    tekshir("SendVenue" in session_obj.metodlar(), "adminga manzil ko'rsatildi")

    print("\n[12.1] Kunlik hisobot")
    await yubor(callback_update(AdmCB(action="sozlamalar").pack()))
    tekshir(
        "Kunlik hisobot" in session_obj.oxirgi_matn() and "✅ yoqilgan" in session_obj.oxirgi_matn(),
        "sozlamalarda hisobot holati ko'rinadi (yoqilgan)",
    )

    await yubor(callback_update(AdmCB(action="hisobot_namuna").pack()))
    namuna = session_obj.oxirgi_matn()
    tekshir(
        "Kunlik hisobot" in namuna and "Jami: <b>2</b> o'quvchi / 4 ariza" in namuna,
        "«Namuna» bugungi hisobotni darhol ko'rsatdi",
    )

    def adminga_hisobot_bordi() -> bool:
        return any(
            nom == "SendMessage"
            and getattr(m, "chat_id", None) == SUPER_ID
            and "Kunlik hisobot" in (m.text or "")
            for nom, m in session_obj.calls
        )

    session_obj.tozalash()
    yuborildi = await hisobot.hisobot_yuborish(bot, config, session_factory)
    tekshir(yuborildi and adminga_hisobot_bordi(), "soat 20:00 dagi hisobot adminga yetib bordi")

    await yubor(callback_update(AdmCB(action="hisobot_toggle").pack()))
    tekshir("❌ o'chiq" in session_obj.oxirgi_matn(), "hisobot o'chirildi")
    session_obj.tozalash()
    yuborildi = await hisobot.hisobot_yuborish(bot, config, session_factory)
    tekshir(not yuborildi and not adminga_hisobot_bordi(), "o'chirilganda hisobot yuborilmaydi")

    await yubor(callback_update(AdmCB(action="hisobot_toggle").pack()))
    tekshir("✅ yoqilgan" in session_obj.oxirgi_matn(), "hisobot qayta yoqildi")

    print("\n[13] Begona odam hech narsa qila olmaydi")
    await yubor(callback_update(AdmCB(action="stat").pack(), user_id=BEGONA_ID))
    tekshir(session_obj.matnlar() == [], "begonaga statistika berilmadi")

    print("\n[14] Broadcast va registratsiyani yopish")
    await yubor(callback_update(AdmCB(action="broadcast").pack()))
    await yubor(matn_update("Assalomu alaykum! Olimpiada 20-oktabrda bo'ladi."))
    tekshir("2</b> ta foydalanuvchiga" in session_obj.oxirgi_matn(), "tasdiq so'raldi")
    await yubor(callback_update(AdmCB(action="broadcast_yes").pack()))
    nusxalar = [nom for nom in session_obj.metodlar() if nom == "CopyMessage"]
    tekshir(len(nusxalar) == 2, f"2 ta foydalanuvchiga yuborildi ({len(nusxalar)})")

    await yubor(callback_update(AdmCB(action="toggle_reg").pack()))
    async with session_factory() as s:
        tekshir(not await sozlama_service.registratsiya_ochiqmi(s), "registratsiya yopildi")
    await yubor(matn_update("/start", user_id=BEGONA_ID))
    tekshir("yopiq" in session_obj.oxirgi_matn().lower(), "yangi o'quvchi ro'yxatdan o'ta olmaydi")

    await bot.session.close()
    await engine.dispose()

    print("\n" + "=" * 55)
    if xatolar:
        print(f"XATOLAR: {len(xatolar)}")
        for x in xatolar:
            print("  -", x)
        sys.exit(1)
    print("ADMIN PANEL ISHLAYAPTI ✅")


if __name__ == "__main__":
    asyncio.run(main())
