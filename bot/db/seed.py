"""Boshlang'ich ma'lumotlar: fanlar ro'yxati va sozlamalar.

Fanni qo'shish/olib tashlash uchun faqat `FANLAR` ro'yxatini tahrirlang.
Ro'yxatdan chiqarilgan fan bazadan O'CHIRILMAYDI, balki yashiriladi
(`faol = False`) — chunki unga bog'langan eski arizalar saqlanib qolishi kerak.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Fan, Sozlama

# (kod, nomi) — kod ariza raqamida ishlatiladi: OT26-MAT-00001
FANLAR: list[tuple[str, str]] = [
    ("MAT", "Matematika"),
    ("ING", "Ingliz tili"),
]

SOZLAMALAR: dict[str, str] = {
    "registratsiya_ochiq": "1",
    # Admin panel -> Sozlamalar -> Yakuniy matn orqali o'zgartiriladi
    "yakun_matni": (
        "❓ <b>Qo'shimcha savollaringiz bo'lsa</b>\n\n"
        "«📞 Aloqa» bo'limi orqali biz bilan bog'laning."
    ),
}


async def seed(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Fanlar va sozlamalarni bazaga yozadi. Har ishga tushishda bajariladi."""
    async with session_factory() as session:
        mavjud = {fan.kod: fan for fan in (await session.scalars(select(Fan))).all()}

        for tartib, (kod, nomi) in enumerate(FANLAR, start=1):
            fan = mavjud.get(kod)
            if fan is None:
                session.add(Fan(kod=kod, nomi=nomi, faol=True, tartib=tartib))
            else:
                fan.nomi = nomi
                fan.faol = True
                fan.tartib = tartib

        kerakli_kodlar = {kod for kod, _ in FANLAR}
        for kod, fan in mavjud.items():
            if kod not in kerakli_kodlar:
                fan.faol = False

        mavjud_kalitlar = set((await session.scalars(select(Sozlama.kalit))).all())
        for kalit, qiymat in SOZLAMALAR.items():
            if kalit not in mavjud_kalitlar:
                session.add(Sozlama(kalit=kalit, qiymat=qiymat))

        await session.commit()
