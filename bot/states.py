"""FSM holatlari."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    """Ro'yxatdan o'tish — 7 qadam."""

    familiya = State()
    ism = State()
    sharif = State()
    telefon = State()
    maktab = State()
    sinf = State()
    fanlar = State()
    tasdiq = State()


class YangiFan(StatesGroup):
    """Ro'yxatdan o'tgandan keyin yangi fan qo'shish."""

    tanlash = State()


class Tahrir(StatesGroup):
    """Profil ma'lumotlarini tahrirlash."""

    maydon_tanlash = State()
    yangi_qiymat = State()


class AdminSt(StatesGroup):
    broadcast_matn = State()
    broadcast_tasdiq = State()
    qidiruv = State()
    rad_sabab = State()
    yangi_admin = State()
    yakun_matni = State()
    manzil = State()
