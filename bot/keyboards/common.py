"""Foydalanuvchi tugmalari."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot import texts as t
from bot.callbacks import ArizaCB, FanCB, NavCB, SinfCB, TahrirCB
from bot.db.models import Ariza, Fan

SINFLAR: tuple[int, ...] = (3, 4, 5, 6, 7)

OLIB_TASHLASH = ReplyKeyboardRemove()

# Tahrirlash uchun maydonlar: (kalit, ko'rinadigan nomi)
TAHRIR_MAYDONLARI: tuple[tuple[str, str], ...] = (
    ("familiya", "👤 Familiya"),
    ("ism", "👤 Ism"),
    ("sharif", "👤 Sharif"),
    ("telefon", "📱 Telefon"),
    ("maktab", "🏫 Maktab"),
    ("sinf", "🎓 Sinf"),
)


def _orqaga_tugma() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=t.ORQAGA, callback_data=NavCB(action="back").pack())


# ---------- Reply (pastki) tugmalar ----------


def bekor_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t.BEKOR)]], resize_keyboard=True
    )


def orqaga_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t.ORQAGA)]], resize_keyboard=True
    )


def telefon_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t.RAQAM_YUBORISH, request_contact=True)],
            [KeyboardButton(text=t.ORQAGA)],
        ],
        resize_keyboard=True,
    )


def asosiy_menyu(*, admin: bool = False) -> ReplyKeyboardMarkup:
    qatorlar = [
        [KeyboardButton(text=t.MENYU_ARIZALARIM), KeyboardButton(text=t.MENYU_YANGI_FAN)],
        [KeyboardButton(text=t.MENYU_TAHRIR), KeyboardButton(text=t.MENYU_ALOQA)],
    ]
    if admin:
        qatorlar.append([KeyboardButton(text=t.MENYU_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=qatorlar, resize_keyboard=True)


# ---------- Inline tugmalar ----------


def sinf_kb() -> InlineKeyboardMarkup:
    tugmalar = [
        InlineKeyboardButton(text=f"{sinf}-sinf", callback_data=SinfCB(sinf=sinf).pack())
        for sinf in SINFLAR
    ]
    # 4 tagacha — bitta qator, ko'proq bo'lsa ikkiga teng bo'linadi (5 ta -> 3+2)
    yarim = len(tugmalar) if len(tugmalar) <= 4 else (len(tugmalar) + 1) // 2
    qatorlar = [q for q in (tugmalar[:yarim], tugmalar[yarim:]) if q]
    qatorlar.append([_orqaga_tugma()])
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def fanlar_kb(
    fanlar: Iterable[Fan], tanlangan: Iterable[int], *, orqaga: bool = True
) -> InlineKeyboardMarkup:
    tanlangan_set = set(tanlangan)
    qatorlar: list[list[InlineKeyboardButton]] = []

    for fan in fanlar:
        belgi = "✅" if fan.id in tanlangan_set else "⬜"
        qatorlar.append(
            [
                InlineKeyboardButton(
                    text=f"{belgi} {fan.nomi}",
                    callback_data=FanCB(action="toggle", fan_id=fan.id).pack(),
                )
            ]
        )

    qatorlar.append(
        [
            InlineKeyboardButton(
                text="✅ Davom etish", callback_data=FanCB(action="done").pack()
            )
        ]
    )
    if orqaga:
        qatorlar.append([_orqaga_tugma()])

    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def tasdiq_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash", callback_data=NavCB(action="confirm").pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Tahrirlash", callback_data=NavCB(action="edit").pack()
                )
            ],
        ]
    )


def tahrir_kb(*, fanlar_ham: bool = False, orqaga_action: str = "back") -> InlineKeyboardMarkup:
    tugmalar = [
        InlineKeyboardButton(text=nomi, callback_data=TahrirCB(maydon=kalit).pack())
        for kalit, nomi in TAHRIR_MAYDONLARI
    ]
    qatorlar = [tugmalar[i : i + 2] for i in range(0, len(tugmalar), 2)]

    if fanlar_ham:
        qatorlar.append(
            [
                InlineKeyboardButton(
                    text="📚 Fanlar", callback_data=TahrirCB(maydon="fanlar").pack()
                )
            ]
        )

    qatorlar.append(
        [
            InlineKeyboardButton(
                text=t.ORQAGA, callback_data=NavCB(action=orqaga_action).pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def arizalar_kb(arizalar: Sequence[Ariza]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🚫 {ariza.fan.nomi} — bekor qilish",
                    callback_data=ArizaCB(action="bekor", ariza_id=ariza.id).pack(),
                )
            ]
            for ariza in arizalar
        ]
    )


def obuna_kb(kanal_havola: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga o'tish", url=kanal_havola)],
            [
                InlineKeyboardButton(
                    text="✅ Tekshirish", callback_data=NavCB(action="check_sub").pack()
                )
            ],
        ]
    )
