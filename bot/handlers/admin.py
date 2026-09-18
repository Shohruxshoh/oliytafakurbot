"""Admin panel.

Ikkita router:
  router       — faqat adminlar uchun (IsAdmin filtri butun routerga qo'yilgan)
  sorov_router — admin bo'lmaganlar uchun: admin bo'lishga ariza yuborish

Rollar:
  super admin — hammasi + broadcast, registratsiyani ochish/yopish, adminlarni boshqarish
  admin       — statistika, Excel, arizalarni tasdiqlash, qidiruv
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import date, timedelta
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import texts as t
from bot.callbacks import AdmCB
from bot.config import Config
from bot.db.models import (
    ADMIN_HOLAT_NOMI,
    ADMIN_ROL_NOMI,
    Admin,
    AdminHolat,
    AdminRol,
    HOLAT_NOMI,
    QATNASHUVCHI_HOLATLAR,
    Ariza,
    Holat,
    User,
)
from bot.keyboards import admin as akb
from bot.services import adminlar as admin_service
from bot.services import arizalar as ariza_service
from bot.services import sozlamalar as sozlama_service
from bot.services import stats as stats_service
from bot.services.export import arizalar_excel
from bot.services.hisobot import HISOBOT_SOATI, hisobot_matni
from bot.states import AdminSt
from bot.utils import vaqt
from bot.utils.yakunlash import manzilni_yuborish

logger = logging.getLogger(__name__)

router = Router(name="admin")
sorov_router = Router(name="admin_sorov")

YUBORISH_ORALIGI = 0.05  # sekund — sekundiga ~20 ta xabar
OXIRGI_ARIZALAR_SONI = 10
EKSPORT_TURLARI = {"eks_kun": "kun", "eks_hafta": "hafta", "eks_oy": "oy", "eks_hammasi": "hammasi"}


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, **data: Any) -> bool:
        session: AsyncSession | None = data.get("session")
        config: Config | None = data.get("config")
        user = data.get("event_from_user")
        if session is None or config is None or user is None:
            return False
        return await admin_service.admin_mi(session, config, user.id)


class IsSuperAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, **data: Any) -> bool:
        session: AsyncSession | None = data.get("session")
        config: Config | None = data.get("config")
        user = data.get("event_from_user")
        if session is None or config is None or user is None:
            return False
        return await admin_service.super_mi(session, config, user.id)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _esc(qiymat: object) -> str:
    return html.escape(str(qiymat or ""))


def _msg(callback: CallbackQuery) -> Message | None:
    return callback.message if isinstance(callback.message, Message) else None


def _chiziq(son: int, eng_katta: int, uzunlik: int = 8) -> str:
    if son <= 0:
        return ""
    if eng_katta <= 0:
        return "▇"
    return "▇" * max(1, round(son * uzunlik / eng_katta))


# ---------------------------------------------------------------- panel


async def _panel_matni(session: AsyncSession, config: Config, telegram_id: int) -> str:
    super_admin = await admin_service.super_mi(session, config, telegram_id)
    rol = "👑 Super admin" if super_admin else "👮 Admin"
    return f"{t.ADMIN_PANEL}\n\nSizning rolingiz: <b>{rol}</b>"


async def _panel_klaviatura(
    session: AsyncSession, config: Config, telegram_id: int
) -> Any:
    super_admin = await admin_service.super_mi(session, config, telegram_id)
    return akb.panel_kb(
        registratsiya_ochiq=await sozlama_service.registratsiya_ochiqmi(session),
        super_admin=super_admin,
        kutayotgan=await admin_service.kutayotganlar_soni(session) if super_admin else 0,
    )


@router.message(StateFilter(None), Command("admin"))
@router.message(StateFilter(None), F.text == t.MENYU_ADMIN)
async def admin_panel(message: Message, session: AsyncSession, config: Config) -> None:
    await message.answer(
        await _panel_matni(session, config, message.from_user.id),
        reply_markup=await _panel_klaviatura(session, config, message.from_user.id),
    )


@router.callback_query(AdmCB.filter(F.action == "panel"))
async def panelga_qaytish(
    callback: CallbackQuery, session: AsyncSession, config: Config
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await xabar.edit_text(
        await _panel_matni(session, config, callback.from_user.id),
        reply_markup=await _panel_klaviatura(session, config, callback.from_user.id),
    )


@router.callback_query(AdmCB.filter(F.action == "bekor"))
async def admin_bekor(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_text("❌ Bekor qilindi.")


# Admin FSM ichida /bekor — qolgan handlerlardan OLDIN turishi shart,
# aks holda «/bekor» rad etish sababi yoki broadcast matni deb qabul qilinadi.
@router.message(StateFilter(AdminSt), Command("bekor"))
async def admin_fsm_bekor(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    await state.clear()
    await message.answer(
        "❌ Bekor qilindi.",
        reply_markup=await _panel_klaviatura(session, config, message.from_user.id),
    )


# ---------------------------------------------------------------- statistika


@router.callback_query(AdmCB.filter(F.action == "stat"))
async def statistika(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    davrlar = await stats_service.qisqacha(session)

    # Holatlar — barchasi (rad etilgan va bekor qilinganlar ham ko'rinsin).
    # Qolgan sanoqlar — faqat qatnashuvchilar.
    holatlar = (
        await session.execute(
            select(Ariza.holat, func.count(Ariza.id)).group_by(Ariza.holat)
        )
    ).all()
    fanlar = await stats_service.fanlar_boyicha(session)
    sinflar = await stats_service.sinflar_boyicha(session)

    belgilar = {"kun": "📅 Bugun", "hafta": "📆 Shu hafta", "oy": "🗓 Shu oy", "hammasi": "📦 Jami"}
    qismlar = ["📊 <b>Statistika</b>\n", "<b>Ro'yxatdan o'tganlar:</b>"]
    for tur, nomi in belgilar.items():
        oquvchi, ariza = davrlar[tur]
        qismlar.append(f"{nomi}: <b>{oquvchi}</b> o'quvchi / {ariza} ariza")

    if holatlar:
        qismlar.append("\n<b>Arizalar holati:</b>")
        qismlar += [f"{HOLAT_NOMI[holat]}: {son}" for holat, son in holatlar]

    if fanlar:
        qismlar.append("\n<b>Fanlar bo'yicha:</b>")
        qismlar += [f"• {_esc(nomi)}: {son}" for nomi, son in fanlar]

    if sinflar:
        qismlar.append("\n<b>Sinflar bo'yicha:</b>")
        qismlar += [f"• {sinf}-sinf: {son}" for sinf, son in sinflar]

    await xabar.edit_text("\n".join(qismlar), reply_markup=akb.stat_kb())


def _davr_jadvali(qatorlar: list[tuple[date, int]], yorliq) -> str:
    eng_katta = max((son for _, son in qatorlar), default=0)
    satrlar = [
        f"{yorliq(sana):<13}{son:>4}  {_chiziq(son, eng_katta)}" for sana, son in qatorlar
    ]
    jami = sum(son for _, son in qatorlar)
    return "<pre>" + "\n".join(satrlar) + "</pre>\n" + f"Jami: <b>{jami}</b> o'quvchi"


@router.callback_query(AdmCB.filter(F.action == "stat_kun"))
async def stat_kunlik(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    qatorlar = await stats_service.kunlar_boyicha(session, kunlar=14)
    jadval = _davr_jadvali(
        qatorlar, lambda s: f"{s.strftime('%d.%m')} {vaqt.kun_nomi(s)}"
    )
    await xabar.edit_text(
        f"📅 <b>Kunlik statistika</b> — oxirgi 14 kun\n\n{jadval}",
        reply_markup=akb.davr_kb("kun"),
    )


@router.callback_query(AdmCB.filter(F.action == "stat_hafta"))
async def stat_haftalik(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    qatorlar = await stats_service.haftalar_boyicha(session, haftalar=8)
    jadval = _davr_jadvali(
        qatorlar,
        lambda s: f"{s.strftime('%d.%m')}–{(s + timedelta(days=6)).strftime('%d.%m')}",
    )
    await xabar.edit_text(
        f"📆 <b>Haftalik statistika</b> — oxirgi 8 hafta\n\n{jadval}",
        reply_markup=akb.davr_kb("hafta"),
    )


@router.callback_query(AdmCB.filter(F.action == "stat_oy"))
async def stat_oylik(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    qatorlar = await stats_service.oylar_boyicha(session, oylar=12)
    jadval = _davr_jadvali(qatorlar, lambda s: vaqt.oy_nomi(s.month, s.year))
    await xabar.edit_text(
        f"🗓 <b>Oylik statistika</b> — oxirgi 12 oy\n\n{jadval}",
        reply_markup=akb.davr_kb("oy"),
    )


# ---------------------------------------------------------------- eksport


@router.callback_query(AdmCB.filter(F.action == "eksport"))
async def eksport_menyusi(callback: CallbackQuery) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await xabar.edit_text(
        "📥 <b>Excel yuklab olish</b>\n\nQaysi davr uchun?", reply_markup=akb.eksport_kb()
    )


@router.callback_query(AdmCB.filter(F.action.in_(set(EKSPORT_TURLARI))))
async def eksport(
    callback: CallbackQuery, callback_data: AdmCB, session: AsyncSession
) -> None:
    tur = EKSPORT_TURLARI[callback_data.action]
    boshlanish, sarlavha = vaqt.davr_chegarasi(tur)

    await callback.answer("Fayl tayyorlanmoqda...")
    xabar = _msg(callback)
    if xabar is None:
        return

    fayl, qatorlar = await arizalar_excel(session, boshlanish=boshlanish)
    if qatorlar == 0:
        await xabar.answer(f"📭 <b>{_esc(sarlavha)}</b> — bu davrda ariza yo'q.")
        return

    nom = f"arizalar_{tur}_{vaqt.hozir().strftime('%Y-%m-%d')}.xlsx"
    await xabar.answer_document(
        BufferedInputFile(fayl.read(), filename=nom),
        caption=f"📥 <b>{_esc(sarlavha)}</b>\nJami: <b>{qatorlar}</b> ta ariza",
    )


# ---------------------------------------------------------------- yangi arizalar


@router.callback_query(AdmCB.filter(F.action == "yangi"))
async def oxirgi_arizalar(callback: CallbackQuery, session: AsyncSession) -> None:
    """Oxirgi ro'yxatdan o'tganlar — soxta yoki dublikat arizalarni topib rad etish uchun."""
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    user_ids = (
        await session.scalars(
            select(Ariza.user_id)
            .where(Ariza.holat != Holat.BEKOR_QILINGAN)
            .group_by(Ariza.user_id)
            .order_by(func.max(Ariza.created_at).desc())
            .limit(OXIRGI_ARIZALAR_SONI)
        )
    ).all()

    if not user_ids:
        await xabar.answer("Hozircha ariza yo'q.")
        return

    await xabar.answer(
        f"🆕 <b>Oxirgi {len(user_ids)} ta o'quvchi</b> — eng yangisi birinchi.\n\n"
        "Arizalar avtomatik qabul qilinadi. Soxta yoki dublikat bo'lsa — ❌ bilan rad eting."
    )
    for user_id in user_ids:
        user = await session.get(User, user_id)
        if user is None:
            continue
        matn, markup = await _user_kartasi(session, user)
        await xabar.answer(matn, reply_markup=markup)


async def _user_kartasi(
    session: AsyncSession, user: User
) -> tuple[str, InlineKeyboardMarkup | None]:
    """O'quvchi haqida ma'lumot va arizalar holatiga mos tugmalar."""
    arizalar = await ariza_service.user_arizalari(session, user.id)
    fanlar = "\n".join(
        f"    • {_esc(a.fan.nomi)} — {HOLAT_NOMI[a.holat]} (<code>{_esc(a.ariza_raqami)}</code>)"
        for a in arizalar
    )
    matn = (
        f"👤 <b>{_esc(user.fish)}</b>\n"
        f"📱 {_esc(user.telefon)}\n"
        f"🏫 {_esc(user.maktab)}\n"
        f"🎓 {user.sinf}-sinf\n"
        f"🕐 {vaqt.mahalliy(user.created_at)}\n"
        f"🔗 {'@' + _esc(user.username) if user.username else 'username yo‘q'}\n"
        f"📚 <b>Arizalar:</b>\n{fanlar or '    —'}"
    )
    markup = akb.user_amal_kb(
        user.id,
        rad_etish=any(a.holat in QATNASHUVCHI_HOLATLAR for a in arizalar),
        qayta_qabul=any(a.holat == Holat.RAD_ETILGAN for a in arizalar),
    )
    return matn, markup


# ---------------------------------------------------------------- rad etish / qayta qabul
# Arizalar avtomatik qabul qilinadi. Admin soxta/dublikat arizani rad etadi,
# xato bilan rad etilganini esa qaytarib qabul qiladi.
# ("tasdiq_user" nomi eski xabarlardagi tugmalar ishlashda davom etishi uchun saqlangan.)


@router.callback_query(AdmCB.filter(F.action == "tasdiq_user"))
async def qayta_qabul(
    callback: CallbackQuery, callback_data: AdmCB, session: AsyncSession, bot: Bot
) -> None:
    user = await session.get(User, callback_data.value)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    arizalar = await ariza_service.user_arizalari(session, user.id)
    # YANGI — avtomatik qabuldan oldin ochilgan eski arizalar
    ozgardi = [a for a in arizalar if a.holat in (Holat.RAD_ETILGAN, Holat.YANGI)]
    if not ozgardi:
        await callback.answer("Arizalari allaqachon qabul qilingan")
        return

    for ariza in ozgardi:
        ariza.holat = Holat.TASDIQLANGAN
        ariza.admin_izohi = None

    await callback.answer(f"{len(ozgardi)} ta ariza qabul qilindi")
    xabar = _msg(callback)
    if xabar is not None:
        matn, markup = await _user_kartasi(session, user)
        await xabar.edit_text(
            f"{matn}\n\n↩️ <b>Qayta qabul qilindi</b> ({_esc(callback.from_user.full_name)})",
            reply_markup=markup,
        )

    fanlar = ", ".join(a.fan.nomi for a in ozgardi)
    await _foydalanuvchiga(
        bot,
        user,
        f"✅ <b>Arizangiz qabul qilindi!</b>\n\n📚 {_esc(fanlar)}\n\n"
        "Olimpiada haqidagi ma'lumotlar shu bot orqali yuboriladi.",
    )


@router.callback_query(AdmCB.filter(F.action == "rad_user"))
async def rad_user_sorash(
    callback: CallbackQuery, callback_data: AdmCB, state: FSMContext
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await state.set_state(AdminSt.rad_sabab)
    await state.update_data(rad_user_id=callback_data.value)
    await xabar.answer(
        "❌ Rad etish sababini yozing (o'quvchiga yuboriladi):\n\n/bekor — bekor qilish"
    )


@router.message(AdminSt.rad_sabab, F.text)
async def rad_sabab_qabul(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    user = await session.get(User, int(data.get("rad_user_id", 0)))
    await state.clear()

    if user is None:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    sabab = (message.text or "").strip()[:500]
    arizalar = await ariza_service.user_arizalari(session, user.id)
    ozgardi = [a for a in arizalar if a.holat in QATNASHUVCHI_HOLATLAR]
    if not ozgardi:
        await message.answer("Bu o'quvchida rad etiladigan ariza yo'q.")
        return

    for ariza in ozgardi:
        ariza.holat = Holat.RAD_ETILGAN
        ariza.admin_izohi = sabab

    await message.answer(
        f"❌ {len(ozgardi)} ta ariza rad etildi.\n"
        "Endi ular statistika va Excel'da hisobga olinmaydi."
    )
    await _foydalanuvchiga(
        bot,
        user,
        f"❌ <b>Arizangiz rad etildi.</b>\n\n💬 Sabab: {_esc(sabab)}\n\n"
        "Savollaringiz bo'lsa, «📞 Aloqa» bo'limiga murojaat qiling.",
    )


async def _foydalanuvchiga(bot: Bot, user: User, matn: str) -> None:
    try:
        await bot.send_message(user.chat_id, matn)
    except TelegramForbiddenError:
        user.bloklangan = True
    except TelegramAPIError as xato:
        logger.warning("Foydalanuvchiga (%s) xabar yuborilmadi: %s", user.telegram_id, xato)


async def _telegramga(bot: Bot, telegram_id: int, matn: str) -> None:
    try:
        await bot.send_message(telegram_id, matn)
    except TelegramAPIError as xato:
        logger.warning("Xabar yuborilmadi (%s): %s", telegram_id, xato)


# ---------------------------------------------------------------- qidiruv


@router.callback_query(AdmCB.filter(F.action == "qidiruv"))
async def qidiruv_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await state.set_state(AdminSt.qidiruv)
    await xabar.answer(t.ADMIN_QIDIRUV_SAVOL + "\n\n/bekor — bekor qilish")


@router.message(AdminSt.qidiruv, F.text)
async def qidiruv_natija(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    soz = (message.text or "").strip()
    if len(soz) < 3:
        await message.answer("Kamida 3 ta belgi kiriting.")
        return

    naqsh = f"%{soz}%"
    users = list(
        (
            await session.scalars(
                select(User)
                .where(
                    or_(
                        User.familiya.ilike(naqsh),
                        User.ism.ilike(naqsh),
                        User.sharif.ilike(naqsh),
                        User.telefon.ilike(naqsh),
                        User.maktab.ilike(naqsh),
                    )
                )
                .limit(10)
            )
        ).all()
    )

    if not users:
        ariza = await session.scalar(select(Ariza).where(Ariza.ariza_raqami.ilike(naqsh)))
        if ariza is not None:
            topilgan = await session.get(User, ariza.user_id)
            if topilgan is not None:
                users = [topilgan]

    if not users:
        await message.answer(t.ADMIN_TOPILMADI)
        return

    for user in users:
        matn, markup = await _user_kartasi(session, user)
        await message.answer(matn, reply_markup=markup)


# ---------------------------------------------------------------- broadcast


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "broadcast"))
async def broadcast_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await state.set_state(AdminSt.broadcast_matn)
    await xabar.answer(t.ADMIN_BROADCAST_SAVOL)


@router.message(AdminSt.broadcast_matn)
async def broadcast_qabul(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    jami = (
        await session.scalar(select(func.count(User.id)).where(User.bloklangan.is_(False)))
        or 0
    )
    await state.update_data(from_chat_id=message.chat.id, message_id=message.message_id)
    await state.set_state(AdminSt.broadcast_tasdiq)
    await message.answer(
        f"📣 Yuqoridagi xabar <b>{jami}</b> ta foydalanuvchiga yuboriladi.\n\nTasdiqlaysizmi?",
        reply_markup=akb.broadcast_tasdiq_kb(),
    )


@router.callback_query(AdminSt.broadcast_tasdiq, AdmCB.filter(F.action == "broadcast_yes"))
async def broadcast_yuborish(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    xabar = _msg(callback)
    if xabar is None:
        return

    from_chat_id = data.get("from_chat_id")
    message_id = data.get("message_id")
    if from_chat_id is None or message_id is None:
        await xabar.edit_text("❌ Xabar topilmadi, qaytadan urinib ko'ring.")
        return

    users = (await session.scalars(select(User).where(User.bloklangan.is_(False)))).all()
    await xabar.edit_text(f"📤 Yuborilmoqda... (0/{len(users)})")

    yuborildi = bloklangan = xatolik = 0
    for nomer, user in enumerate(users, start=1):
        try:
            await bot.copy_message(
                chat_id=user.chat_id, from_chat_id=from_chat_id, message_id=message_id
            )
            yuborildi += 1
        except TelegramRetryAfter as xato:
            await asyncio.sleep(xato.retry_after)
            try:
                await bot.copy_message(
                    chat_id=user.chat_id, from_chat_id=from_chat_id, message_id=message_id
                )
                yuborildi += 1
            except TelegramAPIError:
                xatolik += 1
        except TelegramForbiddenError:
            user.bloklangan = True
            bloklangan += 1
        except TelegramAPIError as xato:
            logger.warning("Broadcast xatosi (%s): %s", user.telegram_id, xato)
            xatolik += 1

        if nomer % 25 == 0:
            try:
                await xabar.edit_text(f"📤 Yuborilmoqda... ({nomer}/{len(users)})")
            except TelegramAPIError:
                pass

        await asyncio.sleep(YUBORISH_ORALIGI)

    await xabar.answer(
        "📣 <b>Yuborish tugadi</b>\n\n"
        f"✅ Yetkazildi: <b>{yuborildi}</b>\n"
        f"🚫 Bloklaganlar: <b>{bloklangan}</b>\n"
        f"⚠️ Xatolik: <b>{xatolik}</b>"
    )


# ---------------------------------------------------------------- registratsiya


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "toggle_reg"))
async def registratsiya_toggle(
    callback: CallbackQuery, session: AsyncSession, config: Config
) -> None:
    ochiq = await sozlama_service.registratsiya_ochiqmi(session)
    await sozlama_service.saqlash(session, "registratsiya_ochiq", "0" if ochiq else "1")

    await callback.answer("Registratsiya " + ("yopildi 🔒" if ochiq else "ochildi ✅"))
    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_reply_markup(
            reply_markup=await _panel_klaviatura(session, config, callback.from_user.id)
        )


# ---------------------------------------------------------------- adminlar


async def _adminlar_matni(session: AsyncSession, config: Config) -> str:
    adminlar = await admin_service.royxat(session)

    qismlar = ["👮 <b>Adminlar</b>\n"]
    qismlar.append(
        f"👑 <b>Doimiy super adminlar</b> (.env dan): {len(config.admin_ids)} ta\n"
        "Ularni botdan o'zgartirib bo'lmaydi."
    )

    if not adminlar:
        qismlar.append("\nQo'shimcha adminlar yo'q.")
    else:
        qismlar.append("")
        for nomer, admin in enumerate(adminlar, start=1):
            qator = (
                f"<b>{nomer}. {_esc(admin.fish)}</b>\n"
                f"    {ADMIN_ROL_NOMI[admin.rol]} · {ADMIN_HOLAT_NOMI[admin.holat]}\n"
                f"    ID: <code>{admin.telegram_id}</code>"
            )
            if admin.username:
                qator += f" · @{_esc(admin.username)}"
            qismlar.append(qator)

    qismlar.append(
        "\n<i>Tugmalar: ✅ tasdiqlash · ❌ rad etish · 👮/👑 rolni almashtirish · 🚫 o'chirish</i>"
    )
    return "\n".join(qismlar)


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "adminlar"))
async def adminlar_royxati(
    callback: CallbackQuery, session: AsyncSession, config: Config
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await xabar.edit_text(
        await _adminlar_matni(session, config),
        reply_markup=akb.adminlar_kb(await admin_service.royxat(session)),
    )


async def _adminlar_yangilash(
    xabar: Message, session: AsyncSession, config: Config
) -> None:
    try:
        await xabar.edit_text(
            await _adminlar_matni(session, config),
            reply_markup=akb.adminlar_kb(await admin_service.royxat(session)),
        )
    except TelegramAPIError:
        await xabar.answer(
            await _adminlar_matni(session, config),
            reply_markup=akb.adminlar_kb(await admin_service.royxat(session)),
        )


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "admin_tasdiq"))
async def admin_tasdiqlash(
    callback: CallbackQuery,
    callback_data: AdmCB,
    session: AsyncSession,
    config: Config,
    bot: Bot,
) -> None:
    admin = await admin_service.tasdiqlash(session, callback_data.value, callback.from_user.id)
    if admin is None:
        await callback.answer("Topilmadi", show_alert=True)
        return

    await callback.answer("✅ Admin tasdiqlandi")
    await _telegramga(
        bot,
        admin.telegram_id,
        "✅ <b>Siz admin etib tayinlandingiz!</b>\n\n"
        "Admin panelga kirish uchun /admin buyrug'ini yuboring.",
    )

    xabar = _msg(callback)
    if xabar is not None:
        await _adminlar_yangilash(xabar, session, config)


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "admin_rad"))
async def admin_rad_etish(
    callback: CallbackQuery,
    callback_data: AdmCB,
    session: AsyncSession,
    config: Config,
    bot: Bot,
) -> None:
    admin = await admin_service.rad_etish(session, callback_data.value, callback.from_user.id)
    if admin is None:
        await callback.answer("Topilmadi", show_alert=True)
        return

    await callback.answer("❌ Rad etildi")
    await _telegramga(bot, admin.telegram_id, "❌ Admin bo'lish arizangiz rad etildi.")

    xabar = _msg(callback)
    if xabar is not None:
        await _adminlar_yangilash(xabar, session, config)


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "admin_ochir"))
async def admin_ochirish(
    callback: CallbackQuery,
    callback_data: AdmCB,
    session: AsyncSession,
    config: Config,
    bot: Bot,
) -> None:
    admin = await session.get(Admin, callback_data.value)
    if admin is None:
        await callback.answer("Topilmadi", show_alert=True)
        return
    if admin.telegram_id == callback.from_user.id:
        await callback.answer("O'zingizni o'chira olmaysiz", show_alert=True)
        return

    telegram_id = admin.telegram_id
    await admin_service.ochirish(session, callback_data.value)
    await callback.answer("🚫 Adminlikdan olindi")
    await _telegramga(bot, telegram_id, "🚫 Sizning adminlik huquqingiz bekor qilindi.")

    xabar = _msg(callback)
    if xabar is not None:
        await _adminlar_yangilash(xabar, session, config)


@router.callback_query(
    IsSuperAdmin(), AdmCB.filter(F.action.in_({"admin_super", "admin_oddiy"}))
)
async def admin_rol_almashtirish(
    callback: CallbackQuery, callback_data: AdmCB, session: AsyncSession, config: Config
) -> None:
    yangi_rol = AdminRol.SUPER if callback_data.action == "admin_super" else AdminRol.ADMIN
    admin = await admin_service.rolni_ozgartirish(session, callback_data.value, yangi_rol)
    if admin is None:
        await callback.answer("Topilmadi", show_alert=True)
        return

    await callback.answer(f"Rol: {ADMIN_ROL_NOMI[yangi_rol]}")
    xabar = _msg(callback)
    if xabar is not None:
        await _adminlar_yangilash(xabar, session, config)


@router.callback_query(IsSuperAdmin(), AdmCB.filter(F.action == "admin_qosh"))
async def admin_qoshish_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await state.set_state(AdminSt.yangi_admin)
    await xabar.answer(
        "➕ Yangi adminning <b>Telegram ID</b> raqamini yuboring.\n\n"
        "ID ni @userinfobot dan bilib olish mumkin.\n"
        "Ixtiyoriy: ID dan keyin probel qo'yib ismini yozing.\n\n"
        "Namuna: <code>123456789 Aliyev Alisher</code>\n\n"
        "/bekor — bekor qilish"
    )


@router.message(AdminSt.yangi_admin, F.text)
async def admin_qoshish(
    message: Message, state: FSMContext, session: AsyncSession, config: Config, bot: Bot
) -> None:
    qismlar = (message.text or "").strip().split(maxsplit=1)
    try:
        telegram_id = int(qismlar[0])
    except (ValueError, IndexError):
        await message.answer("❌ Telegram ID raqam bo'lishi kerak. Qaytadan yuboring:")
        return

    fish = qismlar[1] if len(qismlar) > 1 else f"ID {telegram_id}"
    await state.clear()

    admin, yangi = await admin_service.qoshish(
        session, telegram_id=telegram_id, fish=fish, kim_id=message.from_user.id
    )
    if not yangi:
        await message.answer("ℹ️ Bu foydalanuvchi allaqachon admin.")
    else:
        await message.answer(f"✅ <b>{_esc(admin.fish)}</b> admin etib qo'shildi.")
        await _telegramga(
            bot,
            telegram_id,
            "✅ <b>Siz admin etib tayinlandingiz!</b>\n\n"
            "Admin panelga kirish uchun /admin buyrug'ini yuboring.",
        )

    await message.answer(
        await _panel_matni(session, config, message.from_user.id),
        reply_markup=await _panel_klaviatura(session, config, message.from_user.id),
    )


# ---------------------------------------------------------------- sozlamalar
# Ro'yxatdan o'tgan o'quvchiga yuboriladigan matn va manzil


async def _sozlamalar_ekrani(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    matn = await sozlama_service.yakun_matni(session)
    manzil = await sozlama_service.manzil(session)
    hisobot = await sozlama_service.kunlik_hisobot_yoqilganmi(session)

    if manzil is None:
        manzil_holati = "— kiritilmagan"
    elif manzil.nomi:
        manzil_holati = f"📍 {_esc(manzil.nomi)}"
    else:
        manzil_holati = f"📍 {manzil.lat}, {manzil.lon}"
    matn_holati = "✅ kiritilgan" if matn else "— kiritilmagan"
    hisobot_holati = "✅ yoqilgan" if hisobot else "❌ o'chiq"

    return (
        "⚙️ <b>Sozlamalar</b>\n\n"
        "Bular ro'yxatdan o'tgan o'quvchiga avtomatik yuboriladi:\n\n"
        f"📝 <b>Yakuniy matn:</b> {matn_holati}\n"
        f"📍 <b>Manzil:</b> {manzil_holati}\n\n"
        f"📊 <b>Kunlik hisobot</b> (har kuni {HISOBOT_SOATI}:00 da adminlarga): "
        f"{hisobot_holati}",
        akb.sozlamalar_kb(hisobot_yoqilgan=hisobot),
    )


@router.callback_query(AdmCB.filter(F.action == "sozlamalar"))
async def sozlamalar_menyusi(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    matn, markup = await _sozlamalar_ekrani(session)
    await xabar.edit_text(matn, reply_markup=markup)


@router.callback_query(AdmCB.filter(F.action == "hisobot_toggle"))
async def hisobot_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    yoqildi = await sozlama_service.kunlik_hisobotni_almashtirish(session)
    await callback.answer("Kunlik hisobot " + ("yoqildi ✅" if yoqildi else "o'chirildi"))
    xabar = _msg(callback)
    if xabar is None:
        return
    matn, markup = await _sozlamalar_ekrani(session)
    await xabar.edit_text(matn, reply_markup=markup)


@router.callback_query(AdmCB.filter(F.action == "hisobot_namuna"))
async def hisobot_namuna(callback: CallbackQuery, session: AsyncSession) -> None:
    """Bugungi hisobot hozir qanday ko'rinishini ko'rsatadi (20:00 ni kutmasdan)."""
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await xabar.answer(await hisobot_matni(session))


@router.callback_query(AdmCB.filter(F.action == "yakun_matn"))
async def yakun_matn_sorash(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    joriy = await sozlama_service.yakun_matni(session)
    await state.set_state(AdminSt.yakun_matni)

    await xabar.answer(joriy or "<i>(hozircha matn kiritilmagan)</i>")
    await xabar.answer(
        "📝 <b>Yakuniy matn</b>\n\n"
        "Yuqorida — hozirgi matn. Uni almashtirish uchun yangi matnni yuboring.\n"
        "Qalin, kursiv va havolalar saqlanadi.\n\n"
        "/bekor — bekor qilish",
        reply_markup=akb.sozlama_tahrir_kb("yakun_ochir", ochirish_bor=bool(joriy)),
    )


@router.message(AdminSt.yakun_matni, F.text)
async def yakun_matn_qabul(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    await sozlama_service.yakun_matnini_saqlash(session, message.html_text)
    await state.clear()

    await message.answer("✅ <b>Saqlandi.</b> O'quvchi shuni ko'radi:")
    await message.answer(message.html_text)
    await message.answer(
        await _panel_matni(session, config, message.from_user.id),
        reply_markup=await _panel_klaviatura(session, config, message.from_user.id),
    )


@router.callback_query(AdmCB.filter(F.action == "yakun_ochir"))
async def yakun_matn_ochirish(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await sozlama_service.saqlash(session, sozlama_service.YAKUN_MATNI, "")
    await callback.answer("Matn o'chirildi")

    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_text(
            "🗑 Yakuniy matn o'chirildi — endi o'quvchiga matn yuborilmaydi.",
            reply_markup=akb.sozlama_tahrir_kb("yakun_ochir", ochirish_bor=False),
        )


@router.callback_query(AdmCB.filter(F.action == "manzil"))
async def manzil_sorash(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    joriy = await sozlama_service.manzil(session)
    await state.set_state(AdminSt.manzil)

    if joriy is not None:
        await manzilni_yuborish(bot, xabar.chat.id, joriy)

    await xabar.answer(
        "📍 <b>Manzil</b>\n\n"
        "Lokatsiyani yuboring: 📎 → <b>Location / Joylashuv</b>\n\n"
        "Yoki koordinatani yozing:\n"
        "<code>41.311081, 69.240562</code>\n\n"
        "Nomi bilan:\n"
        "<code>41.311081, 69.240562 | 45-maktab, Chilonzor</code>\n\n"
        "/bekor — bekor qilish",
        reply_markup=akb.sozlama_tahrir_kb("manzil_ochir", ochirish_bor=joriy is not None),
    )


# MUHIM: venue handleri location dan OLDIN turishi kerak —
# venue xabarida `location` maydoni ham to'ldirilgan bo'ladi.
@router.message(AdminSt.manzil, F.venue)
async def manzil_venue(
    message: Message, state: FSMContext, session: AsyncSession, config: Config, bot: Bot
) -> None:
    venue = message.venue
    if venue is None:
        return
    await _manzilni_saqlash(
        message, state, session, config, bot,
        venue.location.latitude, venue.location.longitude, venue.title, venue.address,
    )


@router.message(AdminSt.manzil, F.location)
async def manzil_location(
    message: Message, state: FSMContext, session: AsyncSession, config: Config, bot: Bot
) -> None:
    joylashuv = message.location
    if joylashuv is None:
        return
    await _manzilni_saqlash(
        message, state, session, config, bot,
        joylashuv.latitude, joylashuv.longitude, "", "",
    )


@router.message(AdminSt.manzil, F.text)
async def manzil_matn(
    message: Message, state: FSMContext, session: AsyncSession, config: Config, bot: Bot
) -> None:
    natija = _koordinata_ajratish(message.text or "")
    if natija is None:
        await message.answer(
            "❌ Koordinata topilmadi.\n\n"
            "Namuna: <code>41.311081, 69.240562</code>\n"
            "Yoki 📎 → Location orqali lokatsiya yuboring."
        )
        return

    lat, lon, nomi = natija
    await _manzilni_saqlash(message, state, session, config, bot, lat, lon, nomi, "")


def _koordinata_ajratish(matn: str) -> tuple[float, float, str] | None:
    """«41.311081, 69.240562 | Nomi» ko'rinishidan lat/lon/nom ajratadi.

    Google Maps havolasi ham ishlaydi — ichidagi ikkita son olinadi.
    """
    nomi = ""
    if "|" in matn:
        matn, nomi = matn.split("|", 1)
        nomi = nomi.strip()

    sonlar = re.findall(r"-?\d{1,3}\.\d+", matn)
    if len(sonlar) < 2:
        return None

    lat, lon = float(sonlar[0]), float(sonlar[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon, nomi


async def _manzilni_saqlash(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
    bot: Bot,
    lat: float,
    lon: float,
    nomi: str,
    izohi: str,
) -> None:
    manzil = await sozlama_service.manzil_saqlash(session, lat, lon, nomi, izohi)
    await state.clear()

    await message.answer("✅ <b>Manzil saqlandi.</b> O'quvchi shuni ko'radi:")
    await manzilni_yuborish(bot, message.chat.id, manzil)
    await message.answer(
        await _panel_matni(session, config, message.from_user.id),
        reply_markup=await _panel_klaviatura(session, config, message.from_user.id),
    )


@router.callback_query(AdmCB.filter(F.action == "manzil_ochir"))
async def manzil_ochirish(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await sozlama_service.manzilni_ochirish(session)
    await callback.answer("Manzil o'chirildi")

    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_text(
            "🗑 Manzil o'chirildi — endi o'quvchiga lokatsiya yuborilmaydi.",
            reply_markup=akb.sozlama_tahrir_kb("manzil_ochir", ochirish_bor=False),
        )


# ================================================================
# Admin bo'lmaganlar uchun — ariza yuborish
# ================================================================


@sorov_router.message(StateFilter(None), Command("admin"))
async def admin_emas(message: Message, session: AsyncSession) -> None:
    admin = await admin_service.topish(session, message.from_user.id)

    if admin is not None and admin.holat == AdminHolat.KUTILMOQDA:
        await message.answer("🕐 Arizangiz yuborilgan, super admin tasdiqlashini kuting.")
        return
    if admin is not None and admin.holat == AdminHolat.RAD_ETILGAN:
        await message.answer(
            "❌ Admin bo'lish arizangiz rad etilgan.\n\n"
            "Qaytadan ariza yuborishingiz mumkin:",
            reply_markup=akb.sorov_yuborish_kb(),
        )
        return

    await message.answer(
        "🔒 Sizda admin huquqi yo'q.\n\n"
        "Agar siz tashkilotchilardan bo'lsangiz, ariza yuboring — "
        "super admin ko'rib chiqadi.",
        reply_markup=akb.sorov_yuborish_kb(),
    )


@sorov_router.callback_query(AdmCB.filter(F.action == "sorov"))
async def admin_sorov_yuborish(
    callback: CallbackQuery, session: AsyncSession, config: Config, bot: Bot
) -> None:
    tg = callback.from_user
    admin, yangi = await admin_service.sorov_yaratish(
        session,
        telegram_id=tg.id,
        fish=tg.full_name,
        username=tg.username,
    )

    if not yangi:
        await callback.answer("Arizangiz allaqachon yuborilgan", show_alert=True)
        return

    await callback.answer("Ariza yuborildi")
    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_text(
            "📨 <b>Ariza yuborildi.</b>\n\nSuper admin ko'rib chiqqach xabar beramiz."
        )

    matn = (
        "👮 <b>Admin bo'lish uchun ariza</b>\n\n"
        f"👤 {_esc(admin.fish)}\n"
        f"🆔 <code>{admin.telegram_id}</code>\n"
        f"🔗 {'@' + _esc(admin.username) if admin.username else 'username yo‘q'}"
    )
    for super_id in await admin_service.super_idlari(session, config):
        try:
            await bot.send_message(
                super_id, matn, reply_markup=akb.admin_sorov_kb(admin.id)
            )
        except TelegramAPIError as xato:
            logger.warning("Super adminga (%s) xabar yuborilmadi: %s", super_id, xato)
