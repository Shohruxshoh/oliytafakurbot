"""Arizalar va fanlar bilan ishlash."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Ariza, Fan, Holat, User
from bot.utils.vaqt import hozir


async def faol_fanlar(session: AsyncSession) -> list[Fan]:
    natija = await session.scalars(
        select(Fan).where(Fan.faol.is_(True)).order_by(Fan.tartib, Fan.nomi)
    )
    return list(natija.all())


async def fanlar_by_ids(session: AsyncSession, fan_ids: list[int]) -> list[Fan]:
    if not fan_ids:
        return []
    natija = await session.scalars(
        select(Fan).where(Fan.id.in_(fan_ids)).order_by(Fan.tartib, Fan.nomi)
    )
    return list(natija.all())


async def user_arizalari(session: AsyncSession, user_id: int) -> list[Ariza]:
    """Bekor qilinmagan arizalar."""
    natija = await session.scalars(
        select(Ariza)
        .where(Ariza.user_id == user_id, Ariza.holat != Holat.BEKOR_QILINGAN)
        .order_by(Ariza.id)
    )
    return list(natija.all())


async def band_fan_idlari(session: AsyncSession, user_id: int) -> set[int]:
    """O'quvchi allaqachon yozilgan fanlar (bekor qilinganlari hisobga olinmaydi)."""
    natija = await session.scalars(
        select(Ariza.fan_id).where(
            Ariza.user_id == user_id, Ariza.holat != Holat.BEKOR_QILINGAN
        )
    )
    return set(natija.all())


async def bosh_fanlar(session: AsyncSession, user_id: int) -> list[Fan]:
    """O'quvchi hali yozilmagan faol fanlar."""
    band = await band_fan_idlari(session, user_id)
    return [fan for fan in await faol_fanlar(session) if fan.id not in band]


async def ariza_yaratish(
    session: AsyncSession, user: User, fan_ids: list[int]
) -> list[Ariza]:
    """Tanlangan fanlar uchun ariza ochadi. Dublikat yaratmaydi.

    Ariza darhol qabul qilinadi (TASDIQLANGAN) — admin tasdig'i kerak emas,
    admin faqat soxta/dublikat arizalarni rad etadi.
    Agar avval bekor qilingan ariza bo'lsa — uni qayta faollashtiradi.
    """
    yil = hozir().strftime("%y")
    yangi: list[Ariza] = []

    mavjudlar = {
        ariza.fan_id: ariza
        for ariza in (
            await session.scalars(
                select(Ariza).where(Ariza.user_id == user.id, Ariza.fan_id.in_(fan_ids))
            )
        ).all()
    }

    for fan in await fanlar_by_ids(session, fan_ids):
        mavjud = mavjudlar.get(fan.id)
        if mavjud is not None:
            if mavjud.holat == Holat.BEKOR_QILINGAN:
                mavjud.holat = Holat.TASDIQLANGAN
                mavjud.admin_izohi = None
                yangi.append(mavjud)
            continue

        # fan= va user= darhol beriladi: aks holda keyin ariza.fan.nomi ga
        # murojaat qilinganda async kontekstda lazy-load xatosi chiqadi
        ariza = Ariza(
            user_id=user.id, fan_id=fan.id, fan=fan, user=user, holat=Holat.TASDIQLANGAN
        )
        session.add(ariza)
        await session.flush()
        ariza.ariza_raqami = f"OT{yil}-{fan.kod}-{ariza.id:05d}"
        yangi.append(ariza)

    await session.flush()
    return yangi


async def ariza_bekor_qilish(
    session: AsyncSession, ariza_id: int, user_id: int
) -> Ariza | None:
    ariza = await session.get(Ariza, ariza_id)
    if ariza is None or ariza.user_id != user_id:
        return None
    ariza.holat = Holat.BEKOR_QILINGAN
    await session.flush()
    return ariza
