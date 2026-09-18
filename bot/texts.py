"""Botdagi barcha matnlar shu yerda. Matnni o'zgartirish uchun faqat shu faylni tahrirlang."""

from __future__ import annotations

QADAMLAR_SONI = 7

# ---------- Tugma yozuvlari ----------
ORQAGA = "⬅️ Orqaga"
BEKOR = "❌ Bekor qilish"
RAQAM_YUBORISH = "📱 Raqamni yuborish"

MENYU_ARIZALARIM = "📋 Mening arizalarim"
MENYU_YANGI_FAN = "➕ Yana fan qo'shish"
MENYU_TAHRIR = "✏️ Ma'lumotlarimni tahrirlash"
MENYU_ALOQA = "📞 Aloqa"
MENYU_ADMIN = "🛠 Admin panel"


def qadam(n: int, savol: str) -> str:
    return f"<b>{n}/{QADAMLAR_SONI}-qadam</b>\n\n{savol}"


# ---------- Salomlashuv ----------
SALOM = (
    "🎓 <b>Oliy Tafakkur fan olimpiadasi</b>\n\n"
    "Ro'yxatdan o'tish uchun 7 ta savolga javob berasiz — bu 1 daqiqa vaqt oladi.\n\n"
    "Boshladik 👇"
)

QAYTA_SALOM = "🏠 Asosiy menyu"

REGISTRATSIYA_YOPIQ = (
    "🚫 <b>Ro'yxatga olish hozircha yopiq.</b>\n\n"
    "Yangiliklar uchun kuzatib boring."
)

# ---------- Savollar ----------
SAVOL_FAMILIYA = qadam(1, "👤 <b>Familiyangizni</b> yozing.\n\nNamuna: <i>Aliyev</i>")
SAVOL_ISM = qadam(2, "👤 <b>Ismingizni</b> yozing.\n\nNamuna: <i>Alisher</i>")
SAVOL_SHARIF = qadam(
    3, "👤 <b>Sharifingizni</b> (otangizning ismi) yozing.\n\nNamuna: <i>Akmalovich</i>"
)
SAVOL_TELEFON = qadam(
    4,
    "📱 <b>Telefon raqamingizni</b> yuboring.\n\n"
    "Pastdagi «📱 Raqamni yuborish» tugmasini bosing — shunda xato bo'lmaydi.",
)
SAVOL_MAKTAB = qadam(
    5,
    "🏫 <b>Maktabingizni</b> yozing.\n\nNamuna: <i>Chilonzor tumani, 45-maktab</i>",
)
SAVOL_SINF = qadam(6, "🎓 <b>Nechanchi sinfda</b> o'qiysiz?")
SAVOL_FANLAR = qadam(
    7,
    "📚 <b>Qaysi fandan qatnashmoqchisiz?</b>\n\n"
    "Bir nechta fanni tanlashingiz mumkin.\n"
    "Tanlab bo'lgach «✅ Davom etish» tugmasini bosing.",
)

# ---------- Xatoliklar ----------
XATO_MATN = "❌ Iltimos, matn ko'rinishida yozing."
XATO_ISM = (
    "❌ Faqat harflardan iborat bo'lishi kerak (2–40 ta belgi), raqam va emoji bo'lmasin.\n"
    "Qaytadan yozing:"
)
XATO_TELEFON = (
    "❌ Raqam noto'g'ri.\n\n"
    "«📱 Raqamni yuborish» tugmasini bosing yoki raqamni shu ko'rinishda yozing:\n"
    "<code>+998901234567</code>"
)
XATO_BEGONA_KONTAKT = (
    "❌ Bu boshqa odamning raqami.\n\n"
    "Iltimos, «📱 Raqamni yuborish» tugmasi orqali o'z raqamingizni yuboring."
)
XATO_MAKTAB = "❌ Maktab nomi 3 tadan 100 tagacha belgidan iborat bo'lishi kerak. Qaytadan yozing:"
XATO_FAN_TANLANMAGAN = "❌ Kamida bitta fan tanlang"
XATO_TUGMA = "❌ Iltimos, tugmalardan birini tanlang."

# ---------- Tasdiqlash ----------
TASDIQ_SARLAVHA = "✅ <b>Ma'lumotlaringizni tekshiring:</b>"
TASDIQ_SAVOL = "Hammasi to'g'rimi?"

BEKOR_QILINDI = "❌ Bekor qilindi. Qaytadan boshlash uchun /start bosing."

# ---------- Muvaffaqiyat ----------
RO_YXATDAN_OTDI = "🎉 <b>Tabriklaymiz! Siz ro'yxatdan o'tdingiz.</b>"
RO_YXATDAN_OTDI_IZOH = (
    "Olimpiada haqidagi barcha xabarlar shu bot orqali yuboriladi — "
    "botni <b>bloklamang</b>."
)

# ---------- Menyu ----------
ARIZA_YOQ = "Sizda hali ariza yo'q.\n\n«➕ Yana fan qo'shish» tugmasi orqali qo'shishingiz mumkin."
HAMMA_FAN_TANLANGAN = "✅ Siz mavjud barcha fanlarga yozilgansiz."
YANGI_FAN_SAVOL = "📚 <b>Yana qaysi fandan qatnashmoqchisiz?</b>\n\nTanlab bo'lgach «✅ Davom etish» ni bosing."
FAN_QOSHILDI = "✅ <b>Yangi ariza qabul qilindi!</b>"

TAHRIR_SAVOL = "✏️ <b>Qaysi ma'lumotni o'zgartirmoqchisiz?</b>"
TAHRIR_SAQLANDI = "✅ O'zgartirildi."

ALOQA_MATN = "📞 <b>Aloqa</b>\n\nSavollaringiz bo'lsa murojaat qiling: {aloqa}"

# ---------- Majburiy obuna ----------
OBUNA_KERAK = (
    "📢 Botdan foydalanish uchun kanalimizga obuna bo'ling.\n\n"
    "Obuna bo'lgach «✅ Tekshirish» tugmasini bosing."
)
OBUNA_YOQ = "❌ Siz hali obuna bo'lmadingiz."

# ---------- Admin ----------
ADMIN_PANEL = "🛠 <b>Admin panel</b>"
ADMIN_RUXSAT_YOQ = "❌ Sizda ruxsat yo'q."
ADMIN_BROADCAST_SAVOL = (
    "📣 Yubormoqchi bo'lgan xabarni yozing.\n\n"
    "Matn, rasm yoki video yuborishingiz mumkin.\n"
    "Bekor qilish uchun /bekor"
)
ADMIN_QIDIRUV_SAVOL = "🔎 F.I.Sh., telefon raqam yoki ariza raqamini yozing:"
ADMIN_TOPILMADI = "Hech narsa topilmadi."
