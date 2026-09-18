"""Asosiy menyu: arizalarim, yangi fan qo'shish, ma'lumotlarni tahrirlash, aloqa."""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import texts as t
from bot.callbacks import ArizaCB, FanCB, NavCB, SinfCB, TahrirCB
from bot.config import Config
from bot.db.models import HOLAT_NOMI, User
from bot.keyboards import common as kb
from bot.services import adminlar as admin_service
from bot.services import arizalar as ariza_service
from bot.services import sozlamalar as sozlama_service
from bot.services import users as user_service
from bot.states import Tahrir, YangiFan
from bot.utils.notify import adminlarga
from bot.utils.validators import normalize_ism, normalize_maktab, normalize_telefon
from bot.utils.yakunlash import yakuniy_malumot

router = Router(name="menu")

MAYDON_SAVOLI: dict[str, str] = {
    "familiya": "👤 Yangi <b>familiyangizni</b> yozing:",
    "ism": "👤 Yangi <b>ismingizni</b> yozing:",
    "sharif": "👤 Yangi <b>sharifingizni</b> yozing:",
    "telefon": "📱 Yangi <b>telefon raqamingizni</b> yuboring:",
    "maktab": "🏫 Yangi <b>maktabingizni</b> yozing:",
    "sinf": "🎓 <b>Nechanchi sinfda</b> o'qiysiz?",
}


def _esc(qiymat: object) -> str:
    return html.escape(str(qiymat or ""))


def _msg(callback: CallbackQuery) -> Message | None:
    return callback.message if isinstance(callback.message, Message) else None


async def _menyu(session: AsyncSession, config: Config, telegram_id: int):
    """Asosiy menyu — admin bo'lsa «🛠 Admin panel» tugmasi ham chiqadi."""
    return kb.asosiy_menyu(admin=await admin_service.admin_mi(session, config, telegram_id))


async def _user_yoki_ogohlantirish(
    message: Message, session: AsyncSession
) -> User | None:
    user = await user_service.get_user(session, message.from_user.id)
    if user is None:
        await message.answer(
            "Avval ro'yxatdan o'ting. /start bosing.", reply_markup=kb.OLIB_TASHLASH
        )
    return user


# ---------------------------------------------------------------- arizalarim


@router.message(F.text == t.MENYU_ARIZALARIM)
async def arizalarim(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    user = await _user_yoki_ogohlantirish(message, session)
    if user is None:
        return

    arizalar = await ariza_service.user_arizalari(session, user.id)
    if not arizalar:
        await message.answer(t.ARIZA_YOQ)
        return

    qatorlar = []
    for nomer, ariza in enumerate(arizalar, start=1):
        qator = (
            f"<b>{nomer}. {_esc(ariza.fan.nomi)}</b>\n"
            f"    № <code>{_esc(ariza.ariza_raqami)}</code>\n"
            f"    {HOLAT_NOMI[ariza.holat]}"
        )
        if ariza.admin_izohi:
            qator += f"\n    💬 {_esc(ariza.admin_izohi)}"
        qatorlar.append(qator)

    await message.answer(
        "📋 <b>Sizning arizalaringiz:</b>\n\n" + "\n\n".join(qatorlar),
        reply_markup=kb.arizalar_kb(arizalar),
    )


@router.callback_query(ArizaCB.filter(F.action == "bekor"))
async def ariza_bekor(
    callback: CallbackQuery, callback_data: ArizaCB, session: AsyncSession
) -> None:
    user = await user_service.get_user(session, callback.from_user.id)
    if user is None:
        await callback.answer("Avval ro'yxatdan o'ting", show_alert=True)
        return

    ariza = await ariza_service.ariza_bekor_qilish(session, callback_data.ariza_id, user.id)
    if ariza is None:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return

    await callback.answer("Ariza bekor qilindi")
    xabar = _msg(callback)
    if xabar is not None:
        qolgan = await ariza_service.user_arizalari(session, user.id)
        await xabar.edit_text(
            f"🚫 <b>{_esc(ariza.fan.nomi)}</b> arizasi bekor qilindi.\n\n"
            f"Qolgan arizalaringiz: {len(qolgan)} ta"
        )


# ---------------------------------------------------------------- yangi fan


@router.message(F.text == t.MENYU_YANGI_FAN)
async def yangi_fan(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    user = await _user_yoki_ogohlantirish(message, session)
    if user is None:
        return

    if not await sozlama_service.registratsiya_ochiqmi(session):
        await message.answer(t.REGISTRATSIYA_YOPIQ)
        return

    fanlar = await ariza_service.bosh_fanlar(session, user.id)
    if not fanlar:
        await message.answer(t.HAMMA_FAN_TANLANGAN)
        return

    await state.set_state(YangiFan.tanlash)
    await state.update_data(fan_ids=[])
    await message.answer(
        t.YANGI_FAN_SAVOL, reply_markup=kb.fanlar_kb(fanlar, [], orqaga=False)
    )


@router.callback_query(YangiFan.tanlash, FanCB.filter(F.action == "toggle"))
async def yangi_fan_belgilash(
    callback: CallbackQuery,
    callback_data: FanCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    user = await user_service.get_user(session, callback.from_user.id)
    if user is None:
        await callback.answer()
        return

    data = await state.get_data()
    tanlangan = set(data.get("fan_ids", []))
    if callback_data.fan_id in tanlangan:
        tanlangan.remove(callback_data.fan_id)
    else:
        tanlangan.add(callback_data.fan_id)
    await state.update_data(fan_ids=sorted(tanlangan))

    xabar = _msg(callback)
    if xabar is not None:
        fanlar = await ariza_service.bosh_fanlar(session, user.id)
        await xabar.edit_reply_markup(
            reply_markup=kb.fanlar_kb(fanlar, tanlangan, orqaga=False)
        )
    await callback.answer()


@router.callback_query(YangiFan.tanlash, FanCB.filter(F.action == "done"))
async def yangi_fan_tasdiq(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
    bot: Bot,
) -> None:
    data = await state.get_data()
    fan_ids = data.get("fan_ids", [])
    if not fan_ids:
        await callback.answer(t.XATO_FAN_TANLANMAGAN, show_alert=True)
        return

    user = await user_service.get_user(session, callback.from_user.id)
    if user is None:
        await callback.answer()
        return

    yangi = await ariza_service.ariza_yaratish(session, user, fan_ids)
    await state.clear()
    await callback.answer()

    qatorlar = "\n".join(
        f"• {_esc(ariza.fan.nomi)} — <code>{_esc(ariza.ariza_raqami)}</code>"
        for ariza in yangi
    )
    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_text(f"{t.FAN_QOSHILDI}\n\n{qatorlar}")

    # Admin kiritgan qo'shimcha matn va manzil
    await yakuniy_malumot(bot, session, user.chat_id)

    await adminlarga(
        bot,
        config,
        session,
        (
            "➕ <b>Yangi fan qo'shildi</b>\n\n"
            f"👤 {_esc(user.fish)} — {user.sinf}-sinf\n"
            f"📚 {_esc(', '.join(a.fan.nomi for a in yangi))}"
        ),
    )


# ---------------------------------------------------------------- tahrirlash


@router.message(F.text == t.MENYU_TAHRIR)
async def tahrir_boshlash(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    user = await _user_yoki_ogohlantirish(message, session)
    if user is None:
        return

    await state.set_state(Tahrir.maydon_tanlash)
    await message.answer(
        f"{t.TAHRIR_SAVOL}\n\n"
        f"👤 {_esc(user.fish)}\n"
        f"📱 {_esc(user.telefon)}\n"
        f"🏫 {_esc(user.maktab)}\n"
        f"🎓 {user.sinf}-sinf",
        reply_markup=kb.tahrir_kb(orqaga_action="cancel"),
    )


@router.callback_query(Tahrir.maydon_tanlash, TahrirCB.filter())
async def tahrir_maydon_tanlandi(
    callback: CallbackQuery, callback_data: TahrirCB, state: FSMContext
) -> None:
    savol = MAYDON_SAVOLI.get(callback_data.maydon)
    if savol is None:
        await callback.answer()
        return

    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    await state.update_data(maydon=callback_data.maydon)
    await state.set_state(Tahrir.yangi_qiymat)
    await xabar.edit_text(savol)

    if callback_data.maydon == "sinf":
        await xabar.answer(t.SAVOL_SINF, reply_markup=kb.sinf_kb())
    elif callback_data.maydon == "telefon":
        await xabar.answer("👇", reply_markup=kb.telefon_kb())
    else:
        await xabar.answer("✍️ Yozing:", reply_markup=kb.orqaga_kb())


@router.callback_query(StateFilter(Tahrir), NavCB.filter(F.action == "cancel"))
async def tahrir_bekor(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    await state.clear()
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await xabar.edit_text("🏠 Asosiy menyu")
    await xabar.answer(
        t.QAYTA_SALOM,
        reply_markup=await _menyu(session, config, callback.from_user.id),
    )


@router.message(StateFilter(Tahrir), F.text == t.ORQAGA)
async def tahrir_orqaga(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    await state.clear()
    await message.answer(
        t.QAYTA_SALOM,
        reply_markup=await _menyu(session, config, message.from_user.id),
    )


@router.callback_query(Tahrir.yangi_qiymat, SinfCB.filter())
async def tahrir_sinf(
    callback: CallbackQuery,
    callback_data: SinfCB,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
) -> None:
    if callback_data.sinf not in kb.SINFLAR:
        await callback.answer("Bu sinf ro'yxatda yo'q", show_alert=True)
        return

    user = await user_service.get_user(session, callback.from_user.id)
    if user is None:
        await callback.answer()
        return

    user.sinf = callback_data.sinf
    await state.clear()
    await callback.answer()

    xabar = _msg(callback)
    if xabar is not None:
        await xabar.edit_text(f"✅ Sinf o'zgartirildi: <b>{callback_data.sinf}-sinf</b>")
        await xabar.answer(
            t.TAHRIR_SAQLANDI,
            reply_markup=await _menyu(session, config, callback.from_user.id),
        )


@router.message(Tahrir.yangi_qiymat, F.contact)
async def tahrir_kontakt(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    kontakt = message.contact
    if kontakt is None:
        return
    raqam = normalize_telefon(kontakt.phone_number)
    if raqam is None:
        await message.answer(t.XATO_TELEFON)
        return
    await _tahrir_saqlash(message, state, session, config, "telefon", raqam)


@router.message(Tahrir.yangi_qiymat, F.text)
async def tahrir_matn(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    data = await state.get_data()
    maydon = data.get("maydon")
    matn = message.text or ""

    if maydon in ("familiya", "ism", "sharif"):
        qiymat = normalize_ism(matn)
        xato = t.XATO_ISM
    elif maydon == "maktab":
        qiymat = normalize_maktab(matn)
        xato = t.XATO_MAKTAB
    elif maydon == "telefon":
        qiymat = normalize_telefon(matn)
        xato = t.XATO_TELEFON
    elif maydon == "sinf":
        await message.answer(t.XATO_TUGMA)
        return
    else:
        await state.clear()
        return

    if qiymat is None:
        await message.answer(xato)
        return

    await _tahrir_saqlash(message, state, session, config, maydon, qiymat)


async def _tahrir_saqlash(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
    maydon: str,
    qiymat: str,
) -> None:
    user = await user_service.get_user(session, message.from_user.id)
    if user is None:
        await state.clear()
        return

    setattr(user, maydon, qiymat)
    await state.clear()
    await message.answer(
        f"{t.TAHRIR_SAQLANDI}\n\n<b>{maydon.capitalize()}:</b> {_esc(qiymat)}",
        reply_markup=await _menyu(session, config, message.from_user.id),
    )


# ---------------------------------------------------------------- aloqa


@router.message(F.text == t.MENYU_ALOQA)
async def aloqa(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    await message.answer(t.ALOQA_MATN.format(aloqa=_esc(config.aloqa)))


@router.message(Command("bekor"))
async def bekor_buyrugi(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    await state.clear()
    await message.answer(
        t.QAYTA_SALOM,
        reply_markup=await _menyu(session, config, message.from_user.id),
    )


# ---------------------------------------------------------------- javobsiz qolmasin
# MUHIM: bu handlerlar eng oxirida turishi shart — mos handler topilmagan
# har qanday xabar shu yerga tushadi. Aks holda bot jim qoladi va
# foydalanuvchi "bot ishlamayapti" deb o'ylaydi.


@router.message()
async def tushunmadim(
    message: Message, state: FSMContext, session: AsyncSession, config: Config
) -> None:
    if await state.get_state() is not None:
        await message.answer(
            "👆 Yuqoridagi tugmalardan birini tanlang.\n\n"
            "Bekor qilish uchun /bekor bosing."
        )
        return

    user = await user_service.get_user(session, message.from_user.id)
    if user is None:
        await message.answer("Ro'yxatdan o'tish uchun /start bosing.")
        return

    await message.answer(
        "Quyidagi menyudan tanlang 👇",
        reply_markup=await _menyu(session, config, message.from_user.id),
    )


@router.callback_query()
async def eskirgan_tugma(callback: CallbackQuery) -> None:
    await callback.answer("Bu tugma eskirgan. /start bosing.", show_alert=True)
