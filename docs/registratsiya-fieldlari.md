# Fan olimpiadasi — ro'yxatga olish boti (Oliy Tafakkur)
## Yakuniy spetsifikatsiya — soddalashtirilgan versiya

> Sana: 2026-09-12

### Asosiy tamoyil: minimal ma'lumot, maksimal konversiya

Faqat **6 ta maydon** so'raladi + fan tanlash. Ro'yxatdan o'tish ~1 daqiqa.

### Qabul qilingan qarorlar

| Savol | Qaror |
|---|---|
| Format | Hozircha faqat ro'yxatga olish (test moduli yo'q) |
| To'lov | Bepul |
| Auditoriya | Maktab o'quvchilari, **3–7 sinf** |
| Fan | Bir nechta fan tanlay oladi (cheklovsiz) |
| F.I.Sh. | Alohida 3 ta maydon: Familiya, Ism, Sharif |

### OLIB TASHLANGAN maydonlar

❌ Viloyat ❌ Tuman ❌ Sinf harfi ❌ O'qish tili ❌ Test tili ❌ Jins
❌ Tug'ilgan sana ❌ Ota-ona telefoni ❌ Telefon egasi ❌ Email
❌ Roziliklar (nizom, ota-ona, reklama) ❌ O'qituvchi F.I.Sh. ❌ To'lov maydonlari
❌ JSHSHIR/passport ❌ Imtihon markazi ❌ Sessiya vaqti ❌ Muassasa turi

---

## 1. `users` — o'quvchi profili

### 1.1 Foydalanuvchidan so'raladi — 6 ta maydon

| # | Maydon | Turi | Majburiy | Qanday olinadi | Validatsiya |
|---|---|---|---|---|---|
| 1 | `familiya` | text | ✅ | Matn | 2–40 harf, raqam/emoji rad etiladi |
| 2 | `ism` | text | ✅ | Matn | 2–40 harf |
| 3 | `sharif` | text | ✅ | Matn | 2–40 harf |
| 4 | `telefon` | text | ✅ | **📱 "Raqamni yuborish" tugmasi** | `+998` + operator kodi + 7 raqam |
| 5 | `maktab` | text | ✅ | Matn | 3–100 belgi |
| 6 | `sinf` | int | ✅ | Inline tugmalar 3–7 | 3 ≤ sinf ≤ 7 |

### 1.2 Avtomatik (so'ralmaydi)

| Maydon | Turi | Izoh |
|---|---|---|
| `id` | PK | |
| `telegram_id` | bigint UNIQUE | Asosiy identifikator |
| `chat_id` | bigint | Xabar yuborish uchun |
| `username` | text | `@user` — bo'lmasligi mumkin |
| `manba` | text | `/start instagram` — reklama samarasini o'lchash |
| `bloklangan` | bool | Botni bloklaganlar broadcastda o'tkazib yuboriladi |
| `created_at` / `updated_at` | timestamp | |

---

## 2. `arizalar` — har bir fan uchun alohida yozuv

Bir o'quvchi bir nechta fanga yozilgani uchun ikkinchi jadval kerak.

| Maydon | Turi | Izoh |
|---|---|---|
| `id` | PK | |
| `ariza_raqami` | text UNIQUE | `OT26-MAT-00123` |
| `user_id` | FK → users | |
| `fan_id` | FK → fanlar | |
| `holat` | enum | `tasdiqlangan` (avtomatik) → `rad_etilgan` (admin) ↔ qayta qabul; `bekor_qilingan` (o'quvchi o'zi) |
| `admin_izohi` | text | Rad etish sababi — o'quvchiga yuboriladi |
| `created_at` / `updated_at` | timestamp | |

🔒 **UNIQUE (`user_id`, `fan_id`)** — bitta fanga ikki marta yozila olmaydi.

> Keyingi bosqichda qo'shiladigan ustunlar (hozir kerak emas): `ball`, `orin`, `sertifikat_url`, `qr_kod`.

---

## 3. `fanlar`

| Maydon | Turi | Izoh |
|---|---|---|
| `id` | PK | |
| `kod` | text | `MAT`, `ING` — ariza raqamida ishlatiladi |
| `nomi` | text | |
| `faol` | bool | `false` bo'lsa ro'yxatda ko'rinmaydi |
| `tartib` | int | Ko'rsatilish tartibi |

**Faol fanlar:** Matematika · Ingliz tili

> Ro'yxat `bot/db/seed.py` dagi `FANLAR` da. Undan chiqarilgan fan o'chirilmaydi,
> `faol = False` qilinadi — eski arizalar buzilmasligi uchun.

---

## 4. `sozlamalar` (key–value)

| Kalit | Izoh |
|---|---|
| `registratsiya_ochiq` | Admin ro'yxatni ochadi/yopadi |
| `kunlik_hisobot` | Adminlarga har kuni 20:00 da hisobot (`1` yoqilgan / `0` o'chiq) |
| `yakun_matni` | Ro'yxatdan o'tgach yuboriladigan matn (qo'shimcha savollar uchun) |
| `manzil_lat`, `manzil_lon` | Olimpiada o'tkaziladigan joy koordinatasi |
| `manzil_nomi`, `manzil_izohi` | Joy nomi va manzili — venue sifatida ko'rsatiladi |

Hammasi admin panel → ⚙️ Sozlamalar orqali kiritiladi, koddan emas.

> `.env` dagi `ADMIN_IDS=123456,789012` — doimiy super adminlar.
> Qolgan adminlar `adminlar` jadvalida (7-bo'limga qarang).

---

## 5. Bot oqimi

### Birinchi ro'yxatdan o'tish — 7 qadam

```
/start
 1. Familiya
 2. Ism
 3. Sharif
 4. Telefon          (📱 tugma bosiladi, qo'lda yozilmaydi)
 5. Maktab
 6. Sinf             (inline tugmalar 3–7)
 7. Fan(lar)         (☑️ checkbox — bitta ekranda bir nechta belgilanadi)
 ✅ Tekshiruv ekrani →  Tasdiqlash / Tahrirlash
 🎫 Ariza raqami yuboriladi
```

### Keyingi fan qo'shish — 2 qadam
```
🏠 Menyu → "➕ Yana fan qo'shish" → fan(lar)ni belgilash → Tasdiqlash
```

### Asosiy menyu
`📋 Mening arizalarim` · `➕ Yana fan qo'shish` · `✏️ Ma'lumotlarimni tahrirlash` · `📞 Aloqa`

Har bir qadamda **⬅️ Orqaga** tugmasi va qadam indikatori (`3/7`).

---

## 6. Validatsiya

- **Telefon:** contact share tugmasi asosiy usul; bazada `+998XXXXXXXXX` ko'rinishida saqlanadi
- **F.I.Sh.:** raqam/emoji rad etiladi; `aliyev` → `Aliyev` ga normallashtiriladi
- **Dublikat:** `telefon` bir xil bo'lsa — adminga belgi qo'yiladi (avtomatik bloklanmaydi)
- **Deadline:** `registratsiya_ochiq = false` bo'lsa yangi ariza qabul qilinmaydi

---

## 7. Admin funksiyalari

| Funksiya | Kim uchun | Izoh |
|---|---|---|
| **Statistika** | admin | Bugun / shu hafta / shu oy / jami + fan va sinf kesimlari |
| **Kunlik / haftalik / oylik jadval** | admin | Oxirgi 14 kun, 8 hafta, 12 oy — diagramma bilan |
| **Excel eksport** | admin | Har bir davr uchun alohida: bugun, shu hafta, shu oy, hammasi |
| Rad etish / qayta qabul qilish | admin | Arizalar avtomatik qabul qilinadi; admin faqat soxtasini rad etadi. Sabab o'quvchiga yuboriladi, rad etilgan statistika va Excel'ga kirmaydi |
| **Kunlik hisobot** | admin | Har kuni 20:00 da barcha adminlarga; har bir ro'yxatdan o'tish haqida alohida xabar yo'q |
| Qidiruv | admin | F.I.Sh. / telefon / maktab / ariza raqami bo'yicha |
| **Sozlamalar** | admin | Yakuniy matn va manzil (lokatsiya) — o'quvchiga avtomatik yuboriladi |
| **Broadcast** | super admin | Barcha foydalanuvchilarga |
| Registratsiyani ochish/yopish | super admin | |
| **Adminlarni boshqarish** | super admin | Ariza tasdiqlash, rol berish, o'chirish |

### Rollar

- 👑 **Super admin** — `.env` dagi `ADMIN_IDS` (o'chirib bo'lmaydi) + super qilib ko'tarilganlar
- 👮 **Admin** — super admin tasdiqlagan odamlar

Admin bo'lish: odam `/admin` yozadi -> «Ariza yuborish» -> super adminlarga xabar boradi ->
super admin tasdiqlaydi. Yoki super admin Telegram ID orqali to'g'ridan-to'g'ri qo'shadi.

### `adminlar` jadvali

| Maydon | Izoh |
|---|---|
| `telegram_id` | Unikal |
| `fish`, `username` | Telegram profilidan yoki qo'lda kiritiladi |
| `rol` | `super` / `admin` |
| `holat` | `kutilmoqda` / `tasdiqlangan` / `rad_etilgan` |
| `tasdiqlagan_id` | Kim tasdiqladi |

---

## 8. Texnik qaror

| Komponent | Tanlov |
|---|---|
| Til | Python 3.12 |
| Framework | aiogram 3.x |
| Baza | PostgreSQL (dev uchun SQLite) |
| ORM | SQLAlchemy 2.0 + Alembic |
| Excel | openpyxl |
| Deploy | VPS + Docker yoki systemd, polling |

---

## 9. E'tiborga olinadigan bitta jihat

Viloyat/tuman olib tashlangani uchun **maktab nomi yagona joylashuv ma'lumoti** bo'lib qoladi.
"45-maktab" esa O'zbekistonning deyarli har bir tumanida bor — Excel eksportda ularni
ajrata olmaysiz.

**Yechim (qo'shimcha qadam talab qilmaydi):** maktab so'ralganda savol matnida namuna berilsin:

> «Maktabingizni yozing.
> Namuna: *Chilonzor tumani, 45-maktab*»

Shunda foydalanuvchi tumanni ham o'zi yozib yuboradi, lekin bu alohida qadam bo'lmaydi.
Agar olimpiada bitta shahar/markaz doirasida bo'lsa — bu umuman muammo emas.
