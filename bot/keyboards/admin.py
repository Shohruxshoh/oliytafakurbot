"""Admin panel tugmalari."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import AdmCB
from bot.db.models import Admin, AdminHolat, AdminRol


def _tugma(matn: str, action: str, value: int = 0) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=matn, callback_data=AdmCB(action=action, value=value).pack())


def _orqaga(action: str = "panel") -> list[InlineKeyboardButton]:
    return [_tugma("⬅️ Orqaga", action)]


def panel_kb(
    *, registratsiya_ochiq: bool, super_admin: bool, kutayotgan: int = 0
) -> InlineKeyboardMarkup:
    qatorlar = [
        [_tugma("📊 Statistika", "stat"), _tugma("📥 Excel", "eksport")],
        [_tugma("🆕 Oxirgi arizalar", "yangi"), _tugma("🔎 Qidiruv", "qidiruv")],
        [_tugma("⚙️ Sozlamalar", "sozlamalar")],
    ]

    if super_admin:
        adminlar_matn = "👮 Adminlar"
        if kutayotgan:
            adminlar_matn += f" ({kutayotgan})"
        qatorlar.append(
            [_tugma("📣 Xabar yuborish", "broadcast"), _tugma(adminlar_matn, "adminlar")]
        )
        qatorlar.append(
            [
                _tugma(
                    "🔒 Registratsiyani yopish"
                    if registratsiya_ochiq
                    else "🔓 Registratsiyani ochish",
                    "toggle_reg",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


# ---------------------------------------------------------------- statistika


def stat_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _tugma("📅 Kunlik", "stat_kun"),
                _tugma("📆 Haftalik", "stat_hafta"),
                _tugma("🗓 Oylik", "stat_oy"),
            ],
            _orqaga(),
        ]
    )


def davr_kb(tur: str) -> InlineKeyboardMarkup:
    """Davr statistikasi ostidagi tugmalar: shu davrni Excel'ga yuklab olish."""
    nomlar = {"kun": "bugungi", "hafta": "shu haftadagi", "oy": "shu oydagi"}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_tugma(f"📥 Excel — {nomlar.get(tur, '')} arizalar", f"eks_{tur}")],
            [
                _tugma("📅 Kunlik", "stat_kun"),
                _tugma("📆 Haftalik", "stat_hafta"),
                _tugma("🗓 Oylik", "stat_oy"),
            ],
            _orqaga("stat"),
        ]
    )


# ---------------------------------------------------------------- eksport


def eksport_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_tugma("📅 Bugun", "eks_kun"), _tugma("📆 Shu hafta", "eks_hafta")],
            [_tugma("🗓 Shu oy", "eks_oy"), _tugma("📦 Hammasi", "eks_hammasi")],
            _orqaga(),
        ]
    )


# ---------------------------------------------------------------- arizalar


def user_amal_kb(
    user_id: int, *, rad_etish: bool, qayta_qabul: bool
) -> InlineKeyboardMarkup | None:
    """O'quvchi kartasi ostidagi tugmalar — arizalar holatiga qarab.

    Arizalar avtomatik qabul qilinadi, shuning uchun asosiy amal — rad etish.
    Xato bilan rad etilgan arizani qaytarib qabul qilish mumkin.
    """
    tugmalar = []
    if rad_etish:
        tugmalar.append(_tugma("❌ Rad etish", "rad_user", user_id))
    if qayta_qabul:
        tugmalar.append(_tugma("↩️ Qayta qabul qilish", "tasdiq_user", user_id))
    return InlineKeyboardMarkup(inline_keyboard=[tugmalar]) if tugmalar else None


def broadcast_tasdiq_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_tugma("📣 Ha, yuborilsin", "broadcast_yes")],
            [_tugma("❌ Bekor qilish", "bekor")],
        ]
    )


# ---------------------------------------------------------------- adminlar


def _qisqa(matn: str, uzunlik: int = 14) -> str:
    matn = matn.strip()
    return matn if len(matn) <= uzunlik else matn[: uzunlik - 1] + "…"


def adminlar_kb(adminlar: Sequence[Admin]) -> InlineKeyboardMarkup:
    qatorlar: list[list[InlineKeyboardButton]] = []

    for admin in adminlar:
        nom = _qisqa(admin.fish)
        if admin.holat == AdminHolat.KUTILMOQDA:
            qatorlar.append(
                [
                    _tugma(f"✅ {nom}", "admin_tasdiq", admin.id),
                    _tugma("❌", "admin_rad", admin.id),
                ]
            )
        elif admin.holat == AdminHolat.TASDIQLANGAN:
            yangi_rol = "admin_oddiy" if admin.rol == AdminRol.SUPER else "admin_super"
            belgi = "👑" if admin.rol == AdminRol.SUPER else "👮"
            qatorlar.append(
                [
                    _tugma(f"{belgi} {nom}", yangi_rol, admin.id),
                    _tugma("🚫", "admin_ochir", admin.id),
                ]
            )

    qatorlar.append([_tugma("➕ Admin qo'shish", "admin_qosh")])
    qatorlar.append(_orqaga())
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def admin_sorov_kb(admin_id: int) -> InlineKeyboardMarkup:
    """Super adminga keladigan xabar ostidagi tugmalar."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _tugma("✅ Admin qilish", "admin_tasdiq", admin_id),
                _tugma("❌ Rad etish", "admin_rad", admin_id),
            ]
        ]
    )


# ---------------------------------------------------------------- sozlamalar


def sozlamalar_kb(*, hisobot_yoqilgan: bool) -> InlineKeyboardMarkup:
    hisobot_matni = "📊 Kunlik hisobot: ✅ yoqilgan" if hisobot_yoqilgan else "📊 Kunlik hisobot: ❌ o'chiq"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_tugma("📝 Yakuniy matn", "yakun_matn")],
            [_tugma("📍 Manzil (lokatsiya)", "manzil")],
            [_tugma(hisobot_matni, "hisobot_toggle"), _tugma("👁 Namuna", "hisobot_namuna")],
            _orqaga(),
        ]
    )


def sozlama_tahrir_kb(ochirish_action: str, *, ochirish_bor: bool) -> InlineKeyboardMarkup:
    qatorlar: list[list[InlineKeyboardButton]] = []
    if ochirish_bor:
        qatorlar.append([_tugma("🗑 O'chirish", ochirish_action)])
    qatorlar.append(_orqaga("sozlamalar"))
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def sorov_yuborish_kb() -> InlineKeyboardMarkup:
    """Admin bo'lmagan foydalanuvchi uchun."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[_tugma("📨 Ariza yuborish", "sorov")]]
    )
