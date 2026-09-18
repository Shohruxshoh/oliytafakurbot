"""Bot sozlamalari — koddan emas, admin panelidan boshqariladi.

`sozlamalar` jadvali oddiy kalit-qiymat: matnlar, manzil koordinatalari,
registratsiya ochiq/yopiqligi.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Sozlama

REGISTRATSIYA_OCHIQ = "registratsiya_ochiq"
YAKUN_MATNI = "yakun_matni"
MANZIL_LAT = "manzil_lat"
MANZIL_LON = "manzil_lon"
MANZIL_NOMI = "manzil_nomi"
MANZIL_IZOHI = "manzil_izohi"


@dataclass(frozen=True, slots=True)
class Manzil:
    lat: float
    lon: float
    nomi: str = ""
    izohi: str = ""

    @property
    def sarlavha(self) -> str:
        return self.nomi or "Olimpiada o'tkaziladigan joy"


# ---------- umumiy ----------


async def olish(session: AsyncSession, kalit: str, standart: str = "") -> str:
    qiymat = await session.scalar(select(Sozlama.qiymat).where(Sozlama.kalit == kalit))
    return qiymat if qiymat is not None else standart


async def saqlash(session: AsyncSession, kalit: str, qiymat: str) -> None:
    sozlama = await session.get(Sozlama, kalit)
    if sozlama is None:
        session.add(Sozlama(kalit=kalit, qiymat=qiymat))
    else:
        sozlama.qiymat = qiymat


async def ochirish(session: AsyncSession, *kalitlar: str) -> None:
    for kalit in kalitlar:
        sozlama = await session.get(Sozlama, kalit)
        if sozlama is not None:
            await session.delete(sozlama)
    await session.flush()


# ---------- registratsiya ----------


async def registratsiya_ochiqmi(session: AsyncSession) -> bool:
    return await olish(session, REGISTRATSIYA_OCHIQ, "1") == "1"


# ---------- ro'yxatdan o'tgandan keyingi matn ----------


async def yakun_matni(session: AsyncSession) -> str:
    return await olish(session, YAKUN_MATNI)


async def yakun_matnini_saqlash(session: AsyncSession, matn: str) -> None:
    await saqlash(session, YAKUN_MATNI, matn.strip()[:3000])


# ---------- manzil (lokatsiya) ----------


async def manzil(session: AsyncSession) -> Manzil | None:
    lat = await olish(session, MANZIL_LAT)
    lon = await olish(session, MANZIL_LON)
    if not lat or not lon:
        return None
    try:
        return Manzil(
            lat=float(lat),
            lon=float(lon),
            nomi=await olish(session, MANZIL_NOMI),
            izohi=await olish(session, MANZIL_IZOHI),
        )
    except ValueError:
        return None


async def manzil_saqlash(
    session: AsyncSession, lat: float, lon: float, nomi: str = "", izohi: str = ""
) -> Manzil:
    await saqlash(session, MANZIL_LAT, str(lat))
    await saqlash(session, MANZIL_LON, str(lon))
    await saqlash(session, MANZIL_NOMI, nomi.strip()[:120])
    await saqlash(session, MANZIL_IZOHI, izohi.strip()[:200])
    await session.flush()
    return Manzil(lat=lat, lon=lon, nomi=nomi.strip(), izohi=izohi.strip())


async def manzilni_ochirish(session: AsyncSession) -> None:
    await ochirish(session, MANZIL_LAT, MANZIL_LON, MANZIL_NOMI, MANZIL_IZOHI)
