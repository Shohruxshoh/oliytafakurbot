"""Ro'yxatdan o'tish — 7 qadamli FSM.

Qadamlar: familiya -> ism -> sharif -> telefon -> maktab -> sinf -> fanlar -> tasdiqlash

Har bir qadamda orqaga qaytish mumkin. Tasdiqlash ekranidan istalgan
maydonni tahrirlab, yana tasdiqlash ekraniga qaytiladi.
"""

from __future__ import annotations

import html
from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import texts as t
from bot.callbacks import FanCB, NavCB, SinfCB, TahrirCB
from bot.config import Config
from bot.db.models import Ariza, Fan, User
from bot.keyboards import common as kb
from bot.services import adminlar as admin_service
from bot.services import arizalar as ariza_service
from bot.services import sozlamalar as sozlama_service
from bot.services import users as user_service
from bot.states import Reg
from bot.utils.validators import normalize_ism, normalize_maktab, normalize_telefon
from bot.utils.yakunlash import yakuniy_malumot

router = Router(name="registration")

Savol = Callable[[Message, FSMContext, AsyncSession], Awaitable[None]]


def _esc(qiymat: object) -> str:
    return html.escape(str(qiymat or ""))


def _msg(callback: CallbackQuery) -> Message | None:
    """CallbackQuery ichidagi xabarni qaytaradi (eski xabar bo'lsa None)."""
    return callback.message if isinstance(callback.message, Message) else None


async def _tugmalarni_ochir(xabar: Message) -> None:
    """Inline tugmalarni olib tashlaydi — ikki marta bosilishining oldini oladi."""
    try:
        await xabar.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass  # xabar allaqachon o'zgartirilgan yoki tugmalari yo'q


# ---------------------------------------------------------------- savollar


async def ask_familiya(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    markup = kb.orqaga_kb() if data.get("tahrir") else kb.bekor_kb()
    await state.set_state(Reg.familiya)
    await message.answer(t.SAVOL_FAMILIYA, reply_markup=markup)


async def ask_ism(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(Reg.ism)
    await message.answer(t.SAVOL_ISM, reply_markup=kb.orqaga_kb())


async def ask_sharif(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(Reg.sharif)
    await message.answer(t.SAVOL_SHARIF, reply_markup=kb.orqaga_kb())


async def ask_telefon(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(Reg.telefon)
    await message.answer(t.SAVOL_TELEFON, reply_markup=kb.telefon_kb())


async def ask_maktab(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(Reg.maktab)
    await message.answer(t.SAVOL_MAKTAB, reply_markup=kb.orqaga_kb())


async def ask_sinf(message: Message, state: FSMContext, session: AsyncSession) -> None:
    # Pastdagi «⬅️ Orqaga» tugmasi oldingi qadamdan qolib turadi,
    # shuning uchun bu yerda faqat inline tugmalar yuboriladi.
    await state.set_state(Reg.sinf)
    await message.answer(t.SAVOL_SINF, reply_markup=kb.sinf_kb())


async def ask_fanlar(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    fanlar = await ariza_service.faol_fanlar(session)
    await state.set_state(Reg.fanlar)
    await message.answer(
        t.SAVOL_FANLAR, reply_markup=kb.fanlar_kb(fanlar, data.get("fan_ids", []))
    )


async def ask_tasdiq(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    fanlar = await ariza_service.fanlar_by_ids(session, data.get("fan_ids", []))
    await state.set_state(Reg.tasdiq)
    await message.answer(_xulosa(data, fanlar), reply_markup=kb.tasdiq_kb())


def _xulosa(data: dict, fanlar: list[Fan]) -> str:
    fan_nomlari = ", ".join(fan.nomi for fan in fanlar) or "—"
    return (
        f"{t.TASDIQ_SARLAVHA}\n\n"
        f"👤 <b>F.I.Sh.:</b> {_esc(data.get('familiya'))} "
        f"{_esc(data.get('ism'))} {_esc(data.get('sharif'))}\n"
        f"📱 <b>Telefon:</b> {_esc(data.get('telefon'))}\n"
        f"🏫 <b>Maktab:</b> {_esc(data.get('maktab'))}\n"
        f"🎓 <b>Sinf:</b> {_esc(data.get('sinf'))}-sinf\n"
        f"📚 <b>Fanlar:</b> {_esc(fan_nomlari)}\n\n"
        f"{t.TASDIQ_SAVOL}"
    )


# ---------------------------------------------------------------- /start


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
) -> None:
    await state.clear()
    admin = await admin_service.admin_mi(session, config, message.from_user.id)

    user = await user_service.get_user(session, message.from_user.id)
    if user is not None:
        user.bloklangan = False
        await message.answer(t.QAYTA_SALOM, reply_markup=kb.asosiy_menyu(admin=admin))
        return

    if not await sozlama_service.registratsiya_ochiqmi(session):
        await message.answer(t.REGISTRATSIYA_YOPIQ, reply_markup=kb.OLIB_TASHLASH)
        return

    if command.args:
        await state.update_data(manba=command.args[:64])

    await message.answer(t.SALOM, reply_markup=kb.OLIB_TASHLASH)
    await ask_familiya(message, state, session)


# ------------------------------------------------- bekor qilish / orqaga
# MUHIM: bu handlerlar maydon handlerlaridan OLDIN ro'yxatdan o'tishi kerak


@router.message(StateFilter(Reg), F.text == t.BEKOR)
async def bekor_qilish(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t.BEKOR_QILINDI, reply_markup=kb.OLIB_TASHLASH)


@router.message(StateFilter(Reg), F.text == t.ORQAGA)
async def orqaga_matn(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _orqaga(message, state, session)


@router.callback_query(StateFilter(Reg), NavCB.filter(F.action == "back"))
async def orqaga_tugma(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await _tugmalarni_ochir(xabar)
    await _orqaga(xabar, state, session)


@router.callback_query(StateFilter(Reg), NavCB.filter(F.action == "tasdiq_ekran"))
async def tasdiq_ekraniga(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await _tugmalarni_ochir(xabar)
    await ask_tasdiq(xabar, state, session)


async def _orqaga(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if data.get("tahrir"):
        await state.update_data(tahrir=False)
        await ask_tasdiq(message, state, session)
        return

    joriy = await state.get_state()
    savol = ORQAGA_XARITASI.get(joriy or "")
    if savol is None:
        return
    await savol(message, state, session)


async def _keyingi(
    message: Message, state: FSMContext, session: AsyncSession, joriy: str
) -> None:
    """Keyingi qadamga o'tadi. Tahrirlash rejimida — tasdiqlash ekraniga qaytadi."""
    data = await state.get_data()
    if data.get("tahrir"):
        await state.update_data(tahrir=False)
        await ask_tasdiq(message, state, session)
        return

    savol = KEYINGI_XARITASI.get(joriy)
    if savol is not None:
        await savol(message, state, session)


# ---------------------------------------------------------------- maydonlar


@router.message(Reg.familiya, F.text)
async def familiya_qabul(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    qiymat = normalize_ism(message.text or "")
    if qiymat is None:
        await message.answer(t.XATO_ISM)
        return
    await state.update_data(familiya=qiymat)
    await _keyingi(message, state, session, Reg.familiya.state)


@router.message(Reg.ism, F.text)
async def ism_qabul(message: Message, state: FSMContext, session: AsyncSession) -> None:
    qiymat = normalize_ism(message.text or "")
    if qiymat is None:
        await message.answer(t.XATO_ISM)
        return
    await state.update_data(ism=qiymat)
    await _keyingi(message, state, session, Reg.ism.state)


@router.message(Reg.sharif, F.text)
async def sharif_qabul(message: Message, state: FSMContext, session: AsyncSession) -> None:
    qiymat = normalize_ism(message.text or "")
    if qiymat is None:
        await message.answer(t.XATO_ISM)
        return
    await state.update_data(sharif=qiymat)
    await _keyingi(message, state, session, Reg.sharif.state)


@router.message(Reg.telefon, F.contact)
async def telefon_kontakt(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    kontakt = message.contact
    if kontakt is None:
        return
    if kontakt.user_id is not None and kontakt.user_id != message.from_user.id:
        await message.answer(t.XATO_BEGONA_KONTAKT)
        return

    raqam = normalize_telefon(kontakt.phone_number)
    if raqam is None:
        await message.answer(t.XATO_TELEFON)
        return

    await state.update_data(telefon=raqam)
    await _keyingi(message, state, session, Reg.telefon.state)


@router.message(Reg.telefon, F.text)
async def telefon_matn(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raqam = normalize_telefon(message.text or "")
    if raqam is None:
        await message.answer(t.XATO_TELEFON)
        return
    await state.update_data(telefon=raqam)
    await _keyingi(message, state, session, Reg.telefon.state)


@router.message(Reg.maktab, F.text)
async def maktab_qabul(message: Message, state: FSMContext, session: AsyncSession) -> None:
    qiymat = normalize_maktab(message.text or "")
    if qiymat is None:
        await message.answer(t.XATO_MAKTAB)
        return
    await state.update_data(maktab=qiymat)
    await _keyingi(message, state, session, Reg.maktab.state)


@router.callback_query(Reg.sinf, SinfCB.filter())
async def sinf_tanlandi(
    callback: CallbackQuery,
    callback_data: SinfCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if callback_data.sinf not in kb.SINFLAR:
        await callback.answer("Bu sinf ro'yxatda yo'q", show_alert=True)
        return

    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await state.update_data(sinf=callback_data.sinf)
    await xabar.edit_text(f"🎓 Sinf: <b>{callback_data.sinf}-sinf</b>")
    await _keyingi(xabar, state, session, Reg.sinf.state)


@router.callback_query(Reg.fanlar, FanCB.filter(F.action == "toggle"))
async def fan_belgilash(
    callback: CallbackQuery,
    callback_data: FanCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    tanlangan = set(data.get("fan_ids", []))
    if callback_data.fan_id in tanlangan:
        tanlangan.remove(callback_data.fan_id)
    else:
        tanlangan.add(callback_data.fan_id)
    await state.update_data(fan_ids=sorted(tanlangan))

    xabar = _msg(callback)
    if xabar is not None:
        fanlar = await ariza_service.faol_fanlar(session)
        await xabar.edit_reply_markup(reply_markup=kb.fanlar_kb(fanlar, tanlangan))
    await callback.answer()


@router.callback_query(Reg.fanlar, FanCB.filter(F.action == "done"))
async def fanlar_tugadi(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    if not data.get("fan_ids"):
        await callback.answer(t.XATO_FAN_TANLANMAGAN, show_alert=True)
        return

    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await _tugmalarni_ochir(xabar)
    await _keyingi(xabar, state, session, Reg.fanlar.state)


# ---------------------------------------------------------------- tahrirlash


@router.callback_query(Reg.tasdiq, NavCB.filter(F.action == "edit"))
async def tahrirlash_menyusi(callback: CallbackQuery) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return
    await xabar.edit_text(
        t.TAHRIR_SAVOL,
        reply_markup=kb.tahrir_kb(fanlar_ham=True, orqaga_action="tasdiq_ekran"),
    )


@router.callback_query(Reg.tasdiq, TahrirCB.filter())
async def tahrir_maydon(
    callback: CallbackQuery,
    callback_data: TahrirCB,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    savol = MAYDON_XARITASI.get(callback_data.maydon)
    if savol is None:
        return

    await state.update_data(tahrir=True)
    await _tugmalarni_ochir(xabar)
    await savol(xabar, state, session)


# ---------------------------------------------------------------- tasdiqlash


@router.callback_query(Reg.tasdiq, NavCB.filter(F.action == "confirm"))
async def tasdiqlash(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    config: Config,
    bot: Bot,
) -> None:
    await callback.answer()
    xabar = _msg(callback)
    if xabar is None:
        return

    data = await state.get_data()
    tg = callback.from_user
    kerakli = ("familiya", "ism", "sharif", "telefon", "maktab", "sinf")
    if any(data.get(maydon) in (None, "") for maydon in kerakli) or not data.get("fan_ids"):
        await xabar.answer("❌ Ma'lumotlar to'liq emas. /start bosib qaytadan boshlang.")
        await state.clear()
        return

    user = await user_service.get_user(session, tg.id)
    if user is None:
        user = await user_service.create_user(
            session,
            telegram_id=tg.id,
            chat_id=xabar.chat.id,
            username=tg.username,
            manba=data.get("manba"),
            familiya=data["familiya"],
            ism=data["ism"],
            sharif=data["sharif"],
            telefon=data["telefon"],
            maktab=data["maktab"],
            sinf=int(data["sinf"]),
        )
    else:
        user.familiya = data["familiya"]
        user.ism = data["ism"]
        user.sharif = data["sharif"]
        user.telefon = data["telefon"]
        user.maktab = data["maktab"]
        user.sinf = int(data["sinf"])

    yangi_arizalar = await ariza_service.ariza_yaratish(session, user, data["fan_ids"])
    await state.clear()

    await _tugmalarni_ochir(xabar)
    await xabar.answer(
        _yakuniy_xabar(user, yangi_arizalar),
        reply_markup=kb.asosiy_menyu(
            admin=await admin_service.admin_mi(session, config, tg.id)
        ),
    )
    # Admin kiritgan qo'shimcha matn va manzil (agar kiritilgan bo'lsa)
    await yakuniy_malumot(bot, session, user.chat_id)
    # Adminlarga har bir ro'yxatdan o'tish haqida xabar yuborilmaydi —
    # ular kuniga bir marta hisobot oladi (bot/services/hisobot.py)


def _yakuniy_xabar(user: User, arizalar: list[Ariza]) -> str:
    """Ro'yxat yakunida foydalanuvchiga o'z ma'lumotlari qaytarib ko'rsatiladi."""
    qatorlar = "\n".join(
        f"• {_esc(ariza.fan.nomi)} — <code>{_esc(ariza.ariza_raqami)}</code>"
        for ariza in arizalar
    )
    return (
        f"{t.RO_YXATDAN_OTDI}\n\n"
        f"👤 <b>F.I.Sh.:</b> {_esc(user.fish)}\n"
        f"📱 <b>Telefon:</b> {_esc(user.telefon)}\n"
        f"🏫 <b>Maktab:</b> {_esc(user.maktab)}\n"
        f"🎓 <b>Sinf:</b> {user.sinf}-sinf\n\n"
        f"📚 <b>Arizalaringiz:</b>\n{qatorlar}\n\n"
        f"{t.RO_YXATDAN_OTDI_IZOH}"
    )


# ---------------------------------------------------------------- xaritalar
# (funksiyalardan keyin e'lon qilinadi — ular allaqachon mavjud bo'lishi kerak)

KEYINGI_XARITASI: dict[str, Savol] = {
    Reg.familiya.state: ask_ism,
    Reg.ism.state: ask_sharif,
    Reg.sharif.state: ask_telefon,
    Reg.telefon.state: ask_maktab,
    Reg.maktab.state: ask_sinf,
    Reg.sinf.state: ask_fanlar,
    Reg.fanlar.state: ask_tasdiq,
}

ORQAGA_XARITASI: dict[str, Savol] = {
    Reg.ism.state: ask_familiya,
    Reg.sharif.state: ask_ism,
    Reg.telefon.state: ask_sharif,
    Reg.maktab.state: ask_telefon,
    Reg.sinf.state: ask_maktab,
    Reg.fanlar.state: ask_sinf,
    Reg.tasdiq.state: ask_fanlar,
}

MAYDON_XARITASI: dict[str, Savol] = {
    "familiya": ask_familiya,
    "ism": ask_ism,
    "sharif": ask_sharif,
    "telefon": ask_telefon,
    "maktab": ask_maktab,
    "sinf": ask_sinf,
    "fanlar": ask_fanlar,
}
