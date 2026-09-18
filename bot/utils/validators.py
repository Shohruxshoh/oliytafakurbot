"""Kiritilgan ma'lumotlarni tekshirish va normallashtirish."""

from __future__ import annotations

import re

# O'zbek lotin + kirill harflari, apostroflar, defis va probel
_ISM_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʻʼ'`‘’\- ]{2,40}$")

# O'zbekistondagi mavjud operator kodlari
_OPERATOR_KODLARI = {
    "20", "33", "50", "55", "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
    "88", "90", "91", "93", "94", "95", "97", "98", "99",
}


def normalize_ism(matn: str) -> str | None:
    """Familiya/ism/sharifni tozalaydi. Noto'g'ri bo'lsa None qaytaradi.

    'aliyev  ' -> 'Aliyev',  'ABDULLAYEV' -> 'Abdullayev'
    """
    matn = re.sub(r"\s+", " ", matn.strip())
    if not matn or not _ISM_RE.match(matn):
        return None
    return " ".join(soz.capitalize() for soz in matn.split(" "))


def normalize_telefon(matn: str) -> str | None:
    """Telefon raqamni +998XXXXXXXXX ko'rinishiga keltiradi.

    Qabul qiladi: +998 90 123 45 67 / 998901234567 / 901234567
    """
    raqamlar = re.sub(r"\D", "", matn or "")

    if len(raqamlar) == 9:
        raqamlar = "998" + raqamlar
    elif len(raqamlar) == 12 and raqamlar.startswith("998"):
        pass
    elif len(raqamlar) == 13 and raqamlar.startswith("8998"):
        raqamlar = raqamlar[1:]
    else:
        return None

    if raqamlar[3:5] not in _OPERATOR_KODLARI:
        return None

    return "+" + raqamlar


def normalize_maktab(matn: str) -> str | None:
    """Maktab nomini tozalaydi. 3–100 belgi."""
    matn = re.sub(r"\s+", " ", (matn or "").strip())
    if not 3 <= len(matn) <= 100:
        return None
    return matn
