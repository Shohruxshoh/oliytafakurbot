"""Inline tugmalar uchun callback data fabrikalari."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class NavCB(CallbackData, prefix="nav"):
    """Navigatsiya: back | confirm | edit | cancel | check_sub"""

    action: str


class SinfCB(CallbackData, prefix="sinf"):
    sinf: int


class FanCB(CallbackData, prefix="fan"):
    """action: toggle | done"""

    action: str
    fan_id: int = 0


class TahrirCB(CallbackData, prefix="edit"):
    """maydon: familiya | ism | sharif | telefon | maktab | sinf | fanlar"""

    maydon: str


class ArizaCB(CallbackData, prefix="ariza"):
    """action: bekor"""

    action: str
    ariza_id: int


class AdmCB(CallbackData, prefix="adm"):
    """action: stat | eksport | broadcast | qidiruv | arizalar | tasdiq | rad | sahifa"""

    action: str
    value: int = 0
