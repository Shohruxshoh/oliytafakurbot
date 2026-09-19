"""Kiritilgan ma'lumotlarni tekshirish va normallashtirish."""

from __future__ import annotations

import re

# O'zbek lotin + kirill harflari, apostroflar, defis va probel
_ISM_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʻʼ'`‘’\- ]{2,40}$")

# Operator kodlari ATAYLAB tekshirilmaydi: yangi kodlar (20, 87, ...) muntazam
# qo'shilib turadi va qo'lda yozilgan ro'yxat haqiqiy raqamlarni rad eta boshlaydi.


def normalize_ism(matn: str) -> str | None:
    """Familiya/ism/sharifni tozalaydi. Noto'g'ri bo'lsa None qaytaradi.

    'aliyev  ' -> 'Aliyev',  'ABDULLAYEV' -> 'Abdullayev'
    """
    matn = re.sub(r"\s+", " ", matn.strip())
    if not matn or not _ISM_RE.match(matn):
        return None
    return " ".join(soz.capitalize() for soz in matn.split(" "))


def normalize_telefon(matn: str) -> str | None:
    """QO'LDA yozilgan raqamni +XXXXXXXXXXXX ko'rinishiga keltiradi.

    O'zbekiston: +998 90 123 45 67 / 998901234567 / 901234567 — aniq 12 ta raqam
    (bitta raqam tushib qolsa ham ushlanadi).
    Chet el raqami faqat «+» bilan yozilsa qabul qilinadi: +7 900 123 45 67.
    """
    matn = (matn or "").strip()
    raqamlar = re.sub(r"\D", "", matn)

    if not matn.startswith("+") and len(raqamlar) == 9:
        raqamlar = "998" + raqamlar
    elif len(raqamlar) == 13 and raqamlar.startswith("8998"):
        raqamlar = raqamlar[1:]

    if raqamlar.startswith("998"):
        return "+" + raqamlar if len(raqamlar) == 12 else None

    if matn.startswith("+") and 10 <= len(raqamlar) <= 15:
        return "+" + raqamlar
    return None


def normalize_kontakt(telefon: str) -> str | None:
    """«📱 Raqamni yuborish» tugmasi orqali kelgan O'Z raqami.

    Bu raqamni Telegram SMS orqali tasdiqlagan — shuning uchun faqat formatlanadi,
    mamlakat yoki operator tekshirilmaydi. Telegram raqamni «+» siz ham yuboradi.
    """
    raqamlar = re.sub(r"\D", "", telefon or "")
    if not 7 <= len(raqamlar) <= 15:
        return None
    return "+" + raqamlar


def normalize_maktab(matn: str) -> str | None:
    """Maktab nomini tozalaydi. 3–100 belgi."""
    matn = re.sub(r"\s+", " ", (matn or "").strip())
    if not 3 <= len(matn) <= 100:
        return None
    return matn
