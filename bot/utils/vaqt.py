"""Vaqt bilan ishlash — hamma joyda O'zbekiston (Toshkent) vaqti.

Baza vaqtni UTC da saqlaydi (Docker konteyneri ham UTC da ishlaydi), shuning uchun:
  - ko'rsatishdan oldin  -> Toshkent vaqtiga o'tkaziladi
  - bazaga so'rov qilishdan oldin -> UTC ga o'tkaziladi

Davr chegaralari (kun/hafta/oy boshi) Toshkent vaqti bo'yicha hisoblanadi,
lekin so'rovga UTC ko'rinishida beriladi — aks holda sanoq 5 soatga siljiydi.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TOSHKENT = ZoneInfo("Asia/Tashkent")

HAFTA_KUNLARI = ("Dush", "Sesh", "Chor", "Pay", "Jum", "Shan", "Yak")
OYLAR = (
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
)


def hozir() -> datetime:
    """Hozirgi Toshkent vaqti."""
    return datetime.now(TOSHKENT)


def toshkentga(vaqt: datetime) -> datetime:
    """Bazadan kelgan vaqtni Toshkent vaqtiga o'tkazadi."""
    if vaqt.tzinfo is None:
        vaqt = vaqt.replace(tzinfo=timezone.utc)
    return vaqt.astimezone(TOSHKENT)


def mahalliy(vaqt: datetime | None, shakl: str = "%d.%m.%Y %H:%M") -> str:
    if vaqt is None:
        return ""
    return toshkentga(vaqt).strftime(shakl)


# ---------- davr chegaralari (so'rov uchun, UTC da qaytadi) ----------


def kun_boshi(sana: date | None = None) -> datetime:
    """Toshkent vaqti bo'yicha kun boshi (00:00), UTC da qaytariladi."""
    sana = sana or hozir().date()
    return datetime.combine(sana, time.min, tzinfo=TOSHKENT).astimezone(timezone.utc)


def hafta_boshi(sana: date | None = None) -> datetime:
    """Dushanba 00:00."""
    sana = sana or hozir().date()
    return kun_boshi(sana - timedelta(days=sana.weekday()))


def oy_boshi(sana: date | None = None) -> datetime:
    """Oyning 1-kuni 00:00."""
    sana = sana or hozir().date()
    return kun_boshi(sana.replace(day=1))


def davr_chegarasi(tur: str) -> tuple[datetime | None, str]:
    """(boshlanish, sarlavha) — 'kun' / 'hafta' / 'oy' / 'hammasi'."""
    if tur == "kun":
        return kun_boshi(), f"Bugun ({hozir().strftime('%d.%m.%Y')})"
    if tur == "hafta":
        boshlanish = hafta_boshi()
        return boshlanish, f"Shu hafta ({toshkentga(boshlanish).strftime('%d.%m')} dan)"
    if tur == "oy":
        bugun = hozir()
        return oy_boshi(), f"Shu oy ({OYLAR[bugun.month - 1]} {bugun.year})"
    return None, "Butun davr"


def oy_nomi(oy: int, yil: int | None = None) -> str:
    nomi = OYLAR[oy - 1]
    return f"{nomi} {yil}" if yil else nomi


def kun_nomi(sana: date) -> str:
    return HAFTA_KUNLARI[sana.weekday()]
