"""Tez tekshiruv: importlar, baza, servislar, klaviaturalar, Excel eksport.

Ishga tushirish:  python tests/smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Testlar muhitdan mustaqil bo'lishi kerak: .env yoki Docker env ni bekor qilamiz
os.environ["BOT_TOKEN"] = "123456789:SINOV-TOKENI-HAQIQIY-EMAS"
os.environ["ALOQA"] = "@test"
os.environ["ADMIN_IDS"] = "111,222"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_config
from bot.db.base import create_engine, create_session_factory, init_db
from bot.db.models import AdminHolat, AdminRol, Ariza, Holat
from bot.db.seed import seed
from bot.handlers import admin, menu, registration
from bot.keyboards import admin as akb
from bot.keyboards import common as kb
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services import adminlar as admin_service
from bot.services import arizalar as ariza_service
from bot.services import hisobot
from bot.services import stats as stats_service
from bot.services import sozlamalar as sozlama_service
from bot.services import users as user_service
from bot.services.export import arizalar_excel
from bot.utils import vaqt
from bot.utils.validators import normalize_ism, normalize_maktab, normalize_telefon

xatolar: list[str] = []


def tekshir(shart: bool, tavsif: str) -> None:
    if shart:
        print(f"  ok   {tavsif}")
    else:
        print(f"  XATO {tavsif}")
        xatolar.append(tavsif)


async def main() -> None:
    config = load_config()

    print("\n[1] Validatorlar")
    tekshir(normalize_ism("  aliyev ") == "Aliyev", "ism normallashtirish")
    tekshir(normalize_ism("ABDULLAYEV") == "Abdullayev", "katta harfli ism")
    tekshir(normalize_ism("O'rozov") == "O'rozov", "apostrofli ism")
    tekshir(normalize_ism("Ali 123") is None, "raqamli ism rad etiladi")
    tekshir(normalize_ism("A") is None, "qisqa ism rad etiladi")
    tekshir(normalize_ism("Алиев") == "Алиев", "kirill ism")
    tekshir(normalize_telefon("+998 90 123 45 67") == "+998901234567", "telefon probel bilan")
    tekshir(normalize_telefon("901234567") == "+998901234567", "telefon 9 xonali")
    tekshir(normalize_telefon("998331234567") == "+998331234567", "telefon 998 bilan")
    tekshir(normalize_telefon("+7 900 1234567") is None, "chet el raqami rad etiladi")
    tekshir(normalize_telefon("+998121234567") is None, "noto'g'ri operator kodi rad etiladi")
    tekshir(normalize_maktab("45-maktab") == "45-maktab", "maktab")
    tekshir(normalize_maktab("ab") is None, "qisqa maktab rad etiladi")

    print("\n[2] Baza va seed")
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)
    await init_db(engine)
    await seed(session_factory)

    async with session_factory() as session:
        fanlar = await ariza_service.faol_fanlar(session)
        tekshir(len(fanlar) == 2, f"2 ta fan yuklandi (topildi: {len(fanlar)})")
        tekshir(await sozlama_service.registratsiya_ochiqmi(session), "registratsiya ochiq")

        print("\n[3] Foydalanuvchi va arizalar")
        user = await user_service.create_user(
            session,
            telegram_id=555,
            chat_id=555,
            username="testuser",
            manba="instagram",
            familiya="Aliyev",
            ism="Alisher",
            sharif="Akmalovich",
            telefon="+998901234567",
            maktab="Chilonzor tumani, 45-maktab",
            sinf=5,
        )
        tekshir(user.fish == "Aliyev Alisher Akmalovich", "F.I.Sh. xossasi")

        mat, ing = fanlar[0], fanlar[1]
        arizalar = await ariza_service.ariza_yaratish(session, user, [mat.id, ing.id])
        tekshir(len(arizalar) == 2, "2 ta ariza yaratildi")
        tekshir(
            all(a.holat == Holat.TASDIQLANGAN for a in arizalar),
            "arizalar avtomatik qabul qilindi (admin tasdig'isiz)",
        )
        tekshir(
            all(a.ariza_raqami and a.ariza_raqami.startswith("OT") for a in arizalar),
            f"ariza raqamlari: {[a.ariza_raqami for a in arizalar]}",
        )

        takror = await ariza_service.ariza_yaratish(session, user, [mat.id])
        tekshir(takror == [], "dublikat ariza yaratilmaydi")

        bosh = await ariza_service.bosh_fanlar(session, user.id)
        tekshir(len(bosh) == 0, f"qolgan fanlar: {len(bosh)}")

        bekor = await ariza_service.ariza_bekor_qilish(session, arizalar[0].id, user.id)
        tekshir(bekor is not None and bekor.holat == Holat.BEKOR_QILINGAN, "ariza bekor qilindi")
        tekshir(
            len(await ariza_service.user_arizalari(session, user.id)) == 1,
            "bekor qilingan ariza ro'yxatda ko'rinmaydi",
        )
        qayta = await ariza_service.ariza_yaratish(session, user, [mat.id])
        tekshir(
            len(qayta) == 1 and qayta[0].holat == Holat.TASDIQLANGAN,
            "bekor qilingan ariza qayta ochilganda darhol qabul qilindi",
        )

        begona = await ariza_service.ariza_bekor_qilish(session, arizalar[1].id, user_id=999)
        tekshir(begona is None, "begona arizani bekor qilib bo'lmaydi")

        await session.commit()

    print("\n[4] Vaqt va davr chegaralari")
    tekshir(vaqt.kun_boshi().tzinfo is not None, "kun_boshi UTC-aware qaytadi")
    tekshir(vaqt.kun_boshi() <= vaqt.hozir(), "kun boshi hozirdan oldin")
    tekshir(vaqt.hafta_boshi() <= vaqt.kun_boshi(), "hafta boshi kun boshidan oldin")
    tekshir(vaqt.oy_boshi() <= vaqt.kun_boshi(), "oy boshi kun boshidan oldin")
    tekshir(vaqt.davr_chegarasi("hammasi")[0] is None, "«hammasi» uchun chegara yo'q")
    tekshir(len(vaqt.OYLAR) == 12 and len(vaqt.HAFTA_KUNLARI) == 7, "oy va hafta nomlari")

    print("\n[5] Davr statistikasi")
    async with session_factory() as session:
        qisqacha = await stats_service.qisqacha(session)
        tekshir(set(qisqacha) == {"kun", "hafta", "oy", "hammasi"}, "4 ta davr hisoblandi")
        tekshir(qisqacha["hammasi"] == (1, 2), f"jami: {qisqacha['hammasi']}")
        tekshir(qisqacha["kun"] == (1, 2), f"bugun: {qisqacha['kun']}")

        kunlar = await stats_service.kunlar_boyicha(session, kunlar=14)
        tekshir(len(kunlar) == 14, "14 kunlik jadval")
        tekshir(kunlar[-1][0] == vaqt.hozir().date(), "oxirgi qator — bugun")
        tekshir(sum(s for _, s in kunlar) == 1, "kunlik yig'indi to'g'ri")

        haftalar = await stats_service.haftalar_boyicha(session, haftalar=8)
        tekshir(len(haftalar) == 8, "8 haftalik jadval")
        tekshir(sum(s for _, s in haftalar) == 1, "haftalik yig'indi to'g'ri")
        tekshir(haftalar[-1][0].weekday() == 0, "hafta dushanbadan boshlanadi")

        oylar = await stats_service.oylar_boyicha(session, oylar=12)
        tekshir(len(oylar) == 12, "12 oylik jadval")
        tekshir(sum(s for _, s in oylar) == 1, "oylik yig'indi to'g'ri")
        tekshir(oylar[-1][0].month == vaqt.hozir().month, "oxirgi qator — shu oy")

        print("\n[6] Davr bo'yicha Excel eksport")
        fayl, hammasi = await arizalar_excel(session)
        tekshir(hammasi == 2, f"hammasi: {hammasi} qator")
        tekshir(fayl.getvalue()[:2] == b"PK", "xlsx fayl formati")

        _, bugun = await arizalar_excel(session, boshlanish=vaqt.kun_boshi())
        tekshir(bugun == 2, f"bugungi eksport: {bugun} qator")

        _, hafta = await arizalar_excel(session, boshlanish=vaqt.hafta_boshi())
        tekshir(hafta == 2, f"haftalik eksport: {hafta} qator")

        _, kelajak = await arizalar_excel(
            session, boshlanish=vaqt.kun_boshi() + timedelta(days=1)
        )
        tekshir(kelajak == 0, "kelajakdagi davr bo'sh")

        _, otgan = await arizalar_excel(session, tugash=vaqt.kun_boshi())
        tekshir(otgan == 0, "bugundan oldingi davr bo'sh")

    print("\n[7] Rad etilganlar statistika va Excel'ga kirmaydi")
    async with session_factory() as session:
        soxta_user = await user_service.create_user(
            session,
            telegram_id=556,
            chat_id=556,
            username=None,
            manba=None,
            familiya="Soxtaov",
            ism="Soxta",
            sharif="Soxtaovich",
            telefon="+998901112233",
            maktab="1-maktab",
            sinf=3,
        )
        soxta = await ariza_service.ariza_yaratish(session, soxta_user, [mat.id])
        await session.commit()
        tekshir(
            (await stats_service.qisqacha(session))["hammasi"] == (2, 3),
            "rad etishdan oldin: 2 o'quvchi / 3 ariza",
        )

        soxta[0].holat = Holat.RAD_ETILGAN
        await session.commit()
        tekshir(
            (await stats_service.qisqacha(session))["hammasi"] == (1, 2),
            "rad etilgan o'quvchi ham, arizasi ham sanalmaydi",
        )
        tekshir(
            dict(await stats_service.fanlar_boyicha(session)).get(mat.nomi) == 1,
            "fanlar kesimida ham sanalmaydi",
        )
        tekshir(
            await stats_service.sinflar_boyicha(session) == [(5, 1)],
            "sinflar kesimida ham sanalmaydi",
        )
        tekshir(
            sum(s for _, s in await stats_service.kunlar_boyicha(session)) == 1,
            "kunlik jadvalda ham sanalmaydi",
        )
        _, soni = await arizalar_excel(session)
        tekshir(soni == 2, f"Excel'ga tushmaydi ({soni} qator)")
        _, rad_soni = await arizalar_excel(session, holat=Holat.RAD_ETILGAN)
        tekshir(rad_soni == 1, "kerak bo'lsa rad etilganlarni alohida olish mumkin")

    print("\n[8] Kunlik hisobot")
    async with session_factory() as session:
        matn = await hisobot.hisobot_matni(session)
        tekshir("Kunlik hisobot" in matn, "hisobot sarlavhasi")
        tekshir(
            "Bugun ro'yxatdan o'tdi: <b>1</b> o'quvchi" in matn,
            "bugungi o'quvchilar (rad etilgan sanalmadi)",
        )
        tekshir(f"{mat.nomi}: 1" in matn and f"{ing.nomi}: 1" in matn, "fanlar kesimi")
        tekshir("Jami: <b>1</b> o'quvchi / 2 ariza" in matn, "jami")
        kecha = await hisobot.hisobot_matni(session, vaqt.hozir().date() - timedelta(days=1))
        tekshir("yangi ro'yxatdan o'tganlar yo'q" in kecha, "bo'sh kun uchun alohida matn")

    def soat(s: int, d: int = 0) -> datetime:
        return datetime(2026, 9, 18, s, d, tzinfo=vaqt.TOSHKENT)

    tekshir(hisobot.keyingi_hisobotgacha(soat(19)) == 3600, "19:00 da — 1 soatdan keyin")
    tekshir(
        hisobot.keyingi_hisobotgacha(soat(20)) == 86400,
        "xuddi 20:00 da — keyingisi ertaga (bir kunda ikki marta yubormaydi)",
    )
    tekshir(hisobot.keyingi_hisobotgacha(soat(21, 30)) == 81000, "21:30 da — 22.5 soatdan keyin")

    async with session_factory() as session:
        tekshir(await sozlama_service.kunlik_hisobot_yoqilganmi(session), "sukut bo'yicha yoqilgan")
        tekshir(not await sozlama_service.kunlik_hisobotni_almashtirish(session), "o'chirildi")
        tekshir(await sozlama_service.kunlik_hisobotni_almashtirish(session), "qayta yoqildi")
        await session.commit()

    print("\n[9] Eski 'ko'rib chiqilmoqda' arizalar avtomatik qabul qilinadi")
    async with session_factory() as session:
        eski = (await ariza_service.user_arizalari(session, user.id))[0]
        eski.holat = Holat.YANGI
        await session.commit()
        eski_id = eski.id
    await seed(session_factory)  # bot qayta ishga tushganda bajariladi
    async with session_factory() as session:
        tekshir(
            (await session.get(Ariza, eski_id)).holat == Holat.TASDIQLANGAN,
            "qayta ishga tushganda eski ariza qabul qilindi",
        )

    print("\n[10] Adminlar va rollar")
    async with session_factory() as session:
        admin_service.keshni_tozalash()
        tekshir(await admin_service.admin_mi(session, config, 111), ".env admin — admin")
        tekshir(await admin_service.super_mi(session, config, 111), ".env admin — super")
        tekshir(not await admin_service.admin_mi(session, config, 333), "begona admin emas")

        sorov, yangi = await admin_service.sorov_yaratish(
            session, telegram_id=333, fish="Karimov Aziz", username="aziz"
        )
        tekshir(yangi and sorov.holat == AdminHolat.KUTILMOQDA, "ariza yaratildi")
        tekshir(not await admin_service.admin_mi(session, config, 333), "tasdiqlanmagan admin emas")

        _, takror = await admin_service.sorov_yaratish(
            session, telegram_id=333, fish="Karimov Aziz", username="aziz"
        )
        tekshir(not takror, "takroriy ariza yaratilmaydi")
        tekshir(await admin_service.kutayotganlar_soni(session) == 1, "1 ta ariza kutmoqda")

        await admin_service.tasdiqlash(session, sorov.id, kim_id=111)
        tekshir(await admin_service.admin_mi(session, config, 333), "tasdiqlangandan keyin admin")
        tekshir(not await admin_service.super_mi(session, config, 333), "oddiy admin super emas")
        tekshir(333 in await admin_service.barcha_idlar(session, config), "barcha idlar ro'yxatida")
        tekshir(333 not in await admin_service.super_idlari(session, config), "super idlarda yo'q")

        await admin_service.rolni_ozgartirish(session, sorov.id, AdminRol.SUPER)
        tekshir(await admin_service.super_mi(session, config, 333), "super rolga o'tdi")
        tekshir(333 in await admin_service.super_idlari(session, config), "endi super idlarda")

        await admin_service.ochirish(session, sorov.id)
        tekshir(not await admin_service.admin_mi(session, config, 333), "o'chirilgandan keyin admin emas")

        qoshilgan, _ = await admin_service.qoshish(
            session, telegram_id=444, fish="To'g'ridan-to'g'ri", kim_id=111
        )
        tekshir(
            qoshilgan.holat == AdminHolat.TASDIQLANGAN
            and await admin_service.admin_mi(session, config, 444),
            "super admin to'g'ridan-to'g'ri qo'shdi",
        )

    print("\n[11] Klaviaturalar")
    tekshir(kb.SINFLAR == (3, 4, 5, 6, 7), f"sinflar 3-7: {kb.SINFLAR}")
    tekshir(len(kb.sinf_kb().inline_keyboard) == 3, "sinf klaviaturasi 3+2+orqaga")
    tekshir(
        len(kb.fanlar_kb(fanlar, [fanlar[0].id]).inline_keyboard) == 4,
        "fanlar klaviaturasi (2 fan + davom + orqaga)",
    )
    tekshir(
        "✅" in kb.fanlar_kb(fanlar, [fanlar[0].id]).inline_keyboard[0][0].text,
        "tanlangan fan ✅ bilan belgilanadi",
    )
    tekshir(len(kb.asosiy_menyu(admin=True).keyboard) == 3, "admin menyusi 3 qator")
    tekshir(len(kb.asosiy_menyu().keyboard) == 2, "oddiy menyu 2 qator")
    tekshir(kb.telefon_kb().keyboard[0][0].request_contact is True, "kontakt so'rash tugmasi")

    super_panel = akb.panel_kb(registratsiya_ochiq=True, super_admin=True, kutayotgan=2)
    oddiy_panel = akb.panel_kb(registratsiya_ochiq=True, super_admin=False)
    tekshir(len(super_panel.inline_keyboard) == 5, "super admin paneli 5 qator")
    tekshir(len(oddiy_panel.inline_keyboard) == 3, "oddiy admin paneli 3 qator")
    tekshir(
        any("(2)" in tugma.text for qator in super_panel.inline_keyboard for tugma in qator),
        "kutayotgan arizalar soni ko'rsatiladi",
    )
    tekshir(len(akb.stat_kb().inline_keyboard) == 2, "statistika klaviaturasi")
    tekshir(len(akb.eksport_kb().inline_keyboard) == 3, "eksport klaviaturasi")
    tekshir(len(akb.davr_kb("kun").inline_keyboard) == 3, "davr klaviaturasi")
    sozlama_kb = akb.sozlamalar_kb(hisobot_yoqilgan=True)
    tekshir(len(sozlama_kb.inline_keyboard) == 4, "sozlamalar klaviaturasi")
    tekshir("✅" in sozlama_kb.inline_keyboard[2][0].text, "kunlik hisobot holati tugmada")
    tekshir(
        akb.user_amal_kb(1, rad_etish=False, qayta_qabul=False) is None,
        "amal yo'q — tugma ham yo'q",
    )
    ikkalasi = akb.user_amal_kb(1, rad_etish=True, qayta_qabul=True)
    tekshir(
        ikkalasi is not None and len(ikkalasi.inline_keyboard[0]) == 2,
        "rad etish va qayta qabul tugmalari",
    )

    print("\n[12] Dispatcher va handlerlar")
    tekshir(config.admin_ids == (111, 222), "ADMIN_IDS o'qildi")
    tekshir(config.is_admin(111) and not config.is_admin(333), "is_admin ishlaydi")

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.message.outer_middleware(ThrottlingMiddleware())
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(admin.sorov_router)
    dp.include_router(menu.router)

    turlar = dp.resolve_used_update_types()
    tekshir("message" in turlar and "callback_query" in turlar, f"update turlari: {turlar}")

    reg_h = len(registration.router.message.handlers) + len(registration.router.callback_query.handlers)
    adm_h = len(admin.router.message.handlers) + len(admin.router.callback_query.handlers)
    sorov_h = len(admin.sorov_router.message.handlers) + len(admin.sorov_router.callback_query.handlers)
    menu_h = len(menu.router.message.handlers) + len(menu.router.callback_query.handlers)
    tekshir(reg_h >= 15, f"registratsiya handlerlari: {reg_h}")
    tekshir(adm_h >= 20, f"admin handlerlari: {adm_h}")
    tekshir(sorov_h == 2, f"ariza handlerlari: {sorov_h}")
    tekshir(menu_h >= 12, f"menyu handlerlari: {menu_h}")

    tekshir(
        len(registration.KEYINGI_XARITASI) == 7 and len(registration.ORQAGA_XARITASI) == 7,
        "FSM o'tish xaritalari to'liq",
    )

    await bot.session.close()
    await engine.dispose()

    print("\n" + "=" * 50)
    if xatolar:
        print(f"XATOLAR: {len(xatolar)}")
        for x in xatolar:
            print("  -", x)
        sys.exit(1)
    print("HAMMASI JOYIDA ✅")


if __name__ == "__main__":
    asyncio.run(main())
