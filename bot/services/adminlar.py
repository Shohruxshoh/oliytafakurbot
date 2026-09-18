"""Adminlar bilan ishlash: ruxsat tekshirish, ariza yuborish, tasdiqlash.

.env dagi `ADMIN_IDS` — doimiy super adminlar. Ularni botdan o'chirib bo'lmaydi
va ular har doim barcha huquqlarga ega. Qolgan adminlar bazada saqlanadi va
super admin tomonidan tasdiqlanadi.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import Admin, AdminHolat, AdminRol

# telegram_id -> rol (faqat tasdiqlanganlar). None — hali bazadan o'qilmagan.
# Bot bitta jarayonda ishlagani uchun oddiy kesh yetarli.
_kesh: dict[int, AdminRol] | None = None


def keshni_tozalash() -> None:
    global _kesh
    _kesh = None


async def _rollar(session: AsyncSession) -> dict[int, AdminRol]:
    global _kesh
    if _kesh is None:
        qatorlar = (
            await session.execute(
                select(Admin.telegram_id, Admin.rol).where(
                    Admin.holat == AdminHolat.TASDIQLANGAN
                )
            )
        ).all()
        _kesh = {telegram_id: rol for telegram_id, rol in qatorlar}
    return _kesh


# ---------- ruxsat tekshirish ----------


async def admin_mi(session: AsyncSession, config: Config, telegram_id: int) -> bool:
    if config.is_admin(telegram_id):
        return True
    return telegram_id in await _rollar(session)


async def super_mi(session: AsyncSession, config: Config, telegram_id: int) -> bool:
    if config.is_admin(telegram_id):
        return True
    return (await _rollar(session)).get(telegram_id) == AdminRol.SUPER


async def super_idlari(session: AsyncSession, config: Config) -> list[int]:
    idlar = list(config.admin_ids)
    for telegram_id, rol in (await _rollar(session)).items():
        if rol == AdminRol.SUPER and telegram_id not in idlar:
            idlar.append(telegram_id)
    return idlar


async def barcha_idlar(session: AsyncSession, config: Config) -> list[int]:
    idlar = list(config.admin_ids)
    for telegram_id in await _rollar(session):
        if telegram_id not in idlar:
            idlar.append(telegram_id)
    return idlar


# ---------- boshqaruv ----------


async def royxat(session: AsyncSession) -> list[Admin]:
    """Tasdiq kutayotganlar birinchi bo'lib chiqadi."""
    return list(
        (await session.scalars(select(Admin).order_by(Admin.holat, Admin.id))).all()
    )


async def kutayotganlar_soni(session: AsyncSession) -> int:
    natija = await session.scalars(
        select(Admin.id).where(Admin.holat == AdminHolat.KUTILMOQDA)
    )
    return len(list(natija.all()))


async def topish(session: AsyncSession, telegram_id: int) -> Admin | None:
    return await session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))


async def sorov_yaratish(
    session: AsyncSession, *, telegram_id: int, fish: str, username: str | None
) -> tuple[Admin, bool]:
    """Admin bo'lish uchun ariza. (admin, yangi_arizami) qaytaradi."""
    mavjud = await topish(session, telegram_id)
    if mavjud is not None:
        if mavjud.holat == AdminHolat.RAD_ETILGAN:
            mavjud.holat = AdminHolat.KUTILMOQDA
            mavjud.fish = fish
            mavjud.username = username
            await session.flush()
            return mavjud, True
        return mavjud, False

    admin = Admin(
        telegram_id=telegram_id,
        fish=fish[:128],
        username=username,
        rol=AdminRol.ADMIN,
        holat=AdminHolat.KUTILMOQDA,
    )
    session.add(admin)
    await session.flush()
    return admin, True


async def qoshish(
    session: AsyncSession,
    *,
    telegram_id: int,
    fish: str,
    kim_id: int,
    rol: AdminRol = AdminRol.ADMIN,
) -> tuple[Admin, bool]:
    """Super admin tomonidan to'g'ridan-to'g'ri qo'shish (tasdiq talab qilinmaydi)."""
    mavjud = await topish(session, telegram_id)
    if mavjud is not None:
        yangi = mavjud.holat != AdminHolat.TASDIQLANGAN
        mavjud.holat = AdminHolat.TASDIQLANGAN
        mavjud.tasdiqlagan_id = kim_id
        await session.flush()
        keshni_tozalash()
        return mavjud, yangi

    admin = Admin(
        telegram_id=telegram_id,
        fish=fish[:128],
        rol=rol,
        holat=AdminHolat.TASDIQLANGAN,
        tasdiqlagan_id=kim_id,
    )
    session.add(admin)
    await session.flush()
    keshni_tozalash()
    return admin, True


async def tasdiqlash(session: AsyncSession, admin_id: int, kim_id: int) -> Admin | None:
    admin = await session.get(Admin, admin_id)
    if admin is None:
        return None
    admin.holat = AdminHolat.TASDIQLANGAN
    admin.tasdiqlagan_id = kim_id
    await session.flush()
    keshni_tozalash()
    return admin


async def rad_etish(session: AsyncSession, admin_id: int, kim_id: int) -> Admin | None:
    admin = await session.get(Admin, admin_id)
    if admin is None:
        return None
    admin.holat = AdminHolat.RAD_ETILGAN
    admin.tasdiqlagan_id = kim_id
    await session.flush()
    keshni_tozalash()
    return admin


async def ochirish(session: AsyncSession, admin_id: int) -> Admin | None:
    admin = await session.get(Admin, admin_id)
    if admin is None:
        return None
    await session.delete(admin)
    await session.flush()
    keshni_tozalash()
    return admin


async def rolni_ozgartirish(
    session: AsyncSession, admin_id: int, rol: AdminRol
) -> Admin | None:
    admin = await session.get(Admin, admin_id)
    if admin is None:
        return None
    admin.rol = rol
    await session.flush()
    keshni_tozalash()
    return admin
