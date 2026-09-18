"""Davr bo'yicha statistika: kunlik, haftalik, oylik.

Faqat QATNASHUVCHI arizalar sanaladi — rad etilgan va bekor qilinganlar kirmaydi.
"O'quvchi" — kamida bitta qatnashuvchi arizasi bor foydalanuvchi.

Sanoqlar Toshkent vaqti bo'yicha guruhlanadi (bazada UTC saqlanadi),
shuning uchun guruhlash SQL da emas, Python da qilinadi — bu bir vaqtning
o'zida SQLite va PostgreSQL da bir xil ishlashini ta'minlaydi.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import QATNASHUVCHI_HOLATLAR, Ariza, Fan, User
from bot.utils import vaqt

DAVRLAR = ("kun", "hafta", "oy", "hammasi")


def qatnashuvchi_user_idlari() -> Select:
    """Kamida bitta qatnashuvchi arizasi bor o'quvchilar (subquery)."""
    return select(Ariza.user_id).where(Ariza.holat.in_(QATNASHUVCHI_HOLATLAR))


async def oquvchilar_soni(
    session: AsyncSession,
    boshlanish: datetime | None = None,
    tugash: datetime | None = None,
) -> int:
    """Shu oraliqda ro'yxatdan o'tgan o'quvchilar soni."""
    sorov = select(func.count(User.id)).where(User.id.in_(qatnashuvchi_user_idlari()))
    if boshlanish is not None:
        sorov = sorov.where(User.created_at >= boshlanish)
    if tugash is not None:
        sorov = sorov.where(User.created_at < tugash)
    return await session.scalar(sorov) or 0


async def arizalar_soni(
    session: AsyncSession,
    boshlanish: datetime | None = None,
    tugash: datetime | None = None,
) -> int:
    sorov = select(func.count(Ariza.id)).where(Ariza.holat.in_(QATNASHUVCHI_HOLATLAR))
    if boshlanish is not None:
        sorov = sorov.where(Ariza.created_at >= boshlanish)
    if tugash is not None:
        sorov = sorov.where(Ariza.created_at < tugash)
    return await session.scalar(sorov) or 0


async def fanlar_boyicha(
    session: AsyncSession,
    boshlanish: datetime | None = None,
    tugash: datetime | None = None,
) -> list[tuple[str, int]]:
    """[(fan nomi, arizalar soni)] — ko'pidan kamiga."""
    sorov = (
        select(Fan.nomi, func.count(Ariza.id))
        .join(Ariza, Ariza.fan_id == Fan.id)
        .where(Ariza.holat.in_(QATNASHUVCHI_HOLATLAR))
        .group_by(Fan.nomi)
        .order_by(func.count(Ariza.id).desc())
    )
    if boshlanish is not None:
        sorov = sorov.where(Ariza.created_at >= boshlanish)
    if tugash is not None:
        sorov = sorov.where(Ariza.created_at < tugash)
    return [(nomi, son) for nomi, son in (await session.execute(sorov)).all()]


async def sinflar_boyicha(session: AsyncSession) -> list[tuple[int, int]]:
    sorov = (
        select(User.sinf, func.count(User.id))
        .where(User.id.in_(qatnashuvchi_user_idlari()))
        .group_by(User.sinf)
        .order_by(User.sinf)
    )
    return [(sinf, son) for sinf, son in (await session.execute(sorov)).all()]


async def qisqacha(session: AsyncSession) -> dict[str, tuple[int, int]]:
    """Har bir davr uchun (o'quvchilar soni, arizalar soni)."""
    natija: dict[str, tuple[int, int]] = {}
    for tur in DAVRLAR:
        boshlanish, _ = vaqt.davr_chegarasi(tur)
        natija[tur] = (
            await oquvchilar_soni(session, boshlanish),
            await arizalar_soni(session, boshlanish),
        )
    return natija


async def _royxat_vaqtlari(
    session: AsyncSession, boshlanish: datetime | None
) -> list[datetime]:
    sorov = select(User.created_at).where(User.id.in_(qatnashuvchi_user_idlari()))
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
