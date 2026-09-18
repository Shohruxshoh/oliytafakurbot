"""Davr bo'yicha statistika: kunlik, haftalik, oylik.

Sanoqlar Toshkent vaqti bo'yicha guruhlanadi (bazada UTC saqlanadi),
shuning uchun guruhlash SQL da emas, Python da qilinadi — bu bir vaqtning
o'zida SQLite va PostgreSQL da bir xil ishlashini ta'minlaydi.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Ariza, Holat, User
from bot.utils import vaqt

DAVRLAR = ("kun", "hafta", "oy", "hammasi")


async def _oquvchilar_soni(session: AsyncSession, boshlanish: datetime | None) -> int:
    sorov = select(func.count(User.id))
    if boshlanish is not None:
        sorov = sorov.where(User.created_at >= boshlanish)
    return await session.scalar(sorov) or 0


async def _arizalar_soni(session: AsyncSession, boshlanish: datetime | None) -> int:
    sorov = select(func.count(Ariza.id)).where(Ariza.holat != Holat.BEKOR_QILINGAN)
    if boshlanish is not None:
        sorov = sorov.where(Ariza.created_at >= boshlanish)
    return await session.scalar(sorov) or 0


async def qisqacha(session: AsyncSession) -> dict[str, tuple[int, int]]:
    """Har bir davr uchun (o'quvchilar soni, arizalar soni)."""
    natija: dict[str, tuple[int, int]] = {}
    for tur in DAVRLAR:
        boshlanish, _ = vaqt.davr_chegarasi(tur)
        natija[tur] = (
            await _oquvchilar_soni(session, boshlanish),
            await _arizalar_soni(session, boshlanish),
        )
    return natija


async def _royxat_vaqtlari(
    session: AsyncSession, boshlanish: datetime | None
) -> list[datetime]:
    sorov = select(User.created_at)
    if boshlanish is not None:
        sorov = sorov.where(User.created_at >= boshlanish)
    return [v for v in (await session.scalars(sorov)).all() if v is not None]


async def kunlar_boyicha(
    session: AsyncSession, kunlar: int = 14
) -> list[tuple[date, int]]:
    bugun = vaqt.hozir().date()
    birinchi = bugun - timedelta(days=kunlar - 1)
    vaqtlar = await _royxat_vaqtlari(session, vaqt.kun_boshi(birinchi))

    sanoq = Counter(vaqt.toshkentga(v).date() for v in vaqtlar)
    return [
        (birinchi + timedelta(days=i), sanoq.get(birinchi + timedelta(days=i), 0))
        for i in range(kunlar)
    ]


async def haftalar_boyicha(
    session: AsyncSession, haftalar: int = 8
) -> list[tuple[date, int]]:
    bugun = vaqt.hozir().date()
    shu_hafta = bugun - timedelta(days=bugun.weekday())
    birinchi = shu_hafta - timedelta(weeks=haftalar - 1)
    vaqtlar = await _royxat_vaqtlari(session, vaqt.kun_boshi(birinchi))

    sanoq: Counter[date] = Counter()
    for v in vaqtlar:
        sana = vaqt.toshkentga(v).date()
        sanoq[sana - timedelta(days=sana.weekday())] += 1

    return [
        (birinchi + timedelta(weeks=i), sanoq.get(birinchi + timedelta(weeks=i), 0))
        for i in range(haftalar)
    ]


def _oy_orqaga(sana: date, qadam: int) -> date:
    jami = (sana.year * 12 + sana.month - 1) - qadam
    return date(jami // 12, jami % 12 + 1, 1)


async def oylar_boyicha(
    session: AsyncSession, oylar: int = 12
) -> list[tuple[date, int]]:
    shu_oy = vaqt.hozir().date().replace(day=1)
    birinchi = _oy_orqaga(shu_oy, oylar - 1)
    vaqtlar = await _royxat_vaqtlari(session, vaqt.kun_boshi(birinchi))

    sanoq: Counter[date] = Counter()
    for v in vaqtlar:
        sana = vaqt.toshkentga(v).date()
        sanoq[sana.replace(day=1)] += 1

    royxat = []
    for i in range(oylar):
        oy = _oy_orqaga(shu_oy, oylar - 1 - i)
        royxat.append((oy, sanoq.get(oy, 0)))
    return royxat
