# Oliy Tafakkur — fan olimpiadasi boti

Maktab o'quvchilarini fan olimpiadasiga ro'yxatga oladigan Telegram bot.

- Ro'yxatdan o'tish — **7 qadam**, taxminan 1 daqiqa
- Sinflar: **3–7** · Fanlar: **Matematika, Ingliz tili**
- Bir o'quvchi **bir nechta fanga** yozila oladi
- Admin panel: statistika, **Excel eksport**, ommaviy xabar, arizalarni tasdiqlash

Maydonlar va qarorlar to'liq tavsifi: [docs/registratsiya-fieldlari.md](docs/registratsiya-fieldlari.md)

---

## 1. Sozlash

`.env.example` dan nusxa oling:

```bash
copy .env.example .env
```

`.env` faylni to'ldiring:

| O'zgaruvchi | Izoh |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) da `/newbot` |
| `ADMIN_IDS` | Admin Telegram ID lari, vergul bilan. O'z ID ingiz — [@userinfobot](https://t.me/userinfobot) |
| `ALOQA` | «📞 Aloqa» bo'limida ko'rsatiladigan kontakt |
| `POSTGRES_PASSWORD` | **Docker uchun majburiy** — o'zingiz o'ylab topasiz |
| `DATABASE_URL` | Faqat Docker'siz ishlatganda kerak (SQLite) |

> ⚠️ `.env` faylni hech qachon git'ga qo'shmang — tokeningiz o'g'irlanadi.
> `.gitignore` da allaqachon yozilgan.

---

## 2. Ishga tushirish — Docker (tavsiya etiladi)

Python o'rnatish shart emas, faqat [Docker Desktop](https://www.docker.com/products/docker-desktop/) kerak.

```bash
docker compose up -d --build
```

Shu bitta buyruq: PostgreSQL bazasini ko'taradi, bot image'ini yig'adi, jadvallarni
va fanlar ro'yxatini yaratadi, botni ishga tushiradi.

**Loglarni ko'rish:**

```bash
docker compose logs -f bot
```

**To'xtatish:**

```bash
docker compose down
```

**Kodni o'zgartirgandan keyin qayta yig'ish:**

```bash
docker compose up -d --build bot
```

**Testlarni konteyner ichida ishlatish:**

```bash
docker compose run --rm bot python tests/smoke.py
```

**Baza zaxira nusxasi (backup):**

```bash
docker compose exec db pg_dump -U olimpiada olimpiada > backup.sql
```

> ⚠️ `docker compose down -v` — **bazani ham o'chirib yuboradi**. Barcha arizalar yo'qoladi.
> Oddiy to'xtatish uchun `-v` siz `docker compose down` ishlating.

Bot `restart: unless-stopped` bilan ishlaydi — kompyuter/server qayta yuklansa
o'zi qayta ishga tushadi.

---

## 2.1. Serverga chiqarish

To'liq qo'llanma: **[deploy/DEPLOY.md](deploy/DEPLOY.md)**. Qisqacha (Git Bash'da):

```bash
sed 's/\r$//' deploy/server-setup.sh | ssh root@SERVER_IP 'bash -s'
```

```bash
bash deploy/deploy.sh root@SERVER_IP --baza
```

Birinchisi — serverga Docker o'rnatadi (bir marta). Ikkinchisi — testlarni o'tkazadi,
kompyuterdagi botni to'xtatadi, kod va bazani serverga ko'chiradi. Keyingi yangilashlar
`--baza` siz. Serverda har 24 soatda avtomatik zaxira nusxa olinadi.

---

## 3. Ishga tushirish — Docker'siz

Python 3.11+ kerak.

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
python -m bot.main
```

Bu holatda `.env` dagi `DATABASE_URL` (SQLite) ishlatiladi — baza `bot.db` faylida saqlanadi.

---

## 4. Testlar

Telegram serveriga ulanmaydi, soxta sessiya ishlatiladi:

```bash
python tests/smoke.py
```

```bash
python tests/e2e_registratsiya.py
```

```bash
python tests/e2e_admin.py
```

---

## Foydalanuvchi uchun

```
/start
 1. Familiya      5. Maktab
 2. Ism           6. Sinf (3–7)
 3. Sharif        7. Fan(lar) — bir nechta tanlash mumkin
 4. Telefon       ✅ Tekshiruv ekrani → Tasdiqlash
```

Har qadamda «⬅️ Orqaga» ishlaydi. Tasdiqlash ekranida istalgan maydonni tahrirlash mumkin.

**Asosiy menyu:** 📋 Mening arizalarim · ➕ Yana fan qo'shish · ✏️ Ma'lumotlarimni tahrirlash · 📞 Aloqa

## Admin uchun

`/admin` buyrug'i yoki «🛠 Admin panel» tugmasi.

### Rollar

| Rol | Kim | Nimaga ruxsat |
|---|---|---|
| 👑 **Super admin** | `.env` dagi `ADMIN_IDS` + super qilib ko'tarilganlar | Hammasi |
| 👮 **Admin** | Super admin tasdiqlagan odamlar | Statistika, Excel, arizalarni rad etish, qidiruv, sozlamalar |

`.env` dagi super adminlarni botdan o'chirib bo'lmaydi — bu «kalitni yo'qotib qo'yish»dan himoya.

### Statistika

| Bo'lim | Nima ko'rsatadi |
|---|---|
| 📊 Statistika | 📅 Bugun · 📆 Shu hafta · 🗓 Shu oy · 📦 Jami — har biri uchun o'quvchi va ariza soni. Qo'shimcha: holat, fan va sinf kesimlari |
| 📅 Kunlik | Oxirgi **14 kun**, har bir kun alohida + diagramma |
| 📆 Haftalik | Oxirgi **8 hafta** (dushanbadan yakshanbagacha) |
| 🗓 Oylik | Oxirgi **12 oy** |

Sanoqlar **Toshkent vaqti** bo'yicha guruhlanadi — «bugun» soat 00:00 dan boshlanadi.

### Excel yuklab olish

«📥 Excel» → davrni tanlaysiz: **📅 Bugun · 📆 Shu hafta · 🗓 Shu oy · 📦 Hammasi**.
Har bir davr statistikasi ostida ham «📥 Excel» tugmasi bor — o'sha davrni to'g'ridan-to'g'ri
yuklab olish uchun.

Fayl nomi davr bilan belgilanadi: `arizalar_hafta_2026-09-12.xlsx`

### Arizalar bilan ishlash

Arizalar **avtomatik qabul qilinadi** — o'quvchi darhol `✅ Qabul qilindi` ni ko'radi,
admin hech narsani tasdiqlashi shart emas. Admin faqat soxta, dublikat yoki hazil
arizalarni **rad etadi**. Rad etilgan ariza statistika va Excel'ga kirmaydi, sababi
o'quvchiga yuboriladi. Xato bilan rad etilganini **↩️ Qayta qabul qilish** mumkin.

| Tugma | Vazifasi |
|---|---|
| 🆕 Oxirgi arizalar | Oxirgi 10 ta o'quvchi — soxtasini ❌ bilan rad etish uchun |
| 🔎 Qidiruv | F.I.Sh., telefon, maktab yoki ariza raqami bo'yicha |
| ⚙️ Sozlamalar | Yakuniy matn, manzil va kunlik hisobot (pastda) |
| 📣 Xabar yuborish | Barcha foydalanuvchilarga (faqat super admin) |
| 🔒 Registratsiya | Ro'yxatga olishni ochish/yopish (faqat super admin) |

### 📊 Kunlik hisobot

Har bir ro'yxatdan o'tish haqida alohida xabar kelmaydi. O'rniga **har kuni soat 20:00 da**
barcha adminlarga bitta hisobot keladi: bugun nechta o'quvchi ro'yxatdan o'tdi, fanlar
kesimida, va jami. ⚙️ Sozlamalar'da o'chirib qo'yish mumkin, **👁 Namuna** tugmasi esa
bugungi hisobotni 20:00 ni kutmasdan ko'rsatadi.

### ⚙️ Sozlamalar — ro'yxat yakunida yuboriladigan narsalar

O'quvchi ro'yxatdan o'tgach bot **uchta xabar** yuboradi:

1. Tabrik + o'quvchining o'z ma'lumotlari va ariza raqamlari
2. **📝 Yakuniy matn** — qo'shimcha savollar uchun (admin kiritadi)
3. **📍 Manzil** — olimpiada o'tkaziladigan joy, xaritada (admin kiritadi)

**Matnni kiritish:** ⚙️ Sozlamalar → 📝 Yakuniy matn → yangi matnni yuboring.
Qalin, kursiv va havolalar saqlanadi.

**Manzilni kiritish:** ⚙️ Sozlamalar → 📍 Manzil → 📎 → **Location** orqali lokatsiya
yuboring. Yoki koordinatani yozing:

```
41.311081, 69.240562 | 45-maktab, Chilonzor
```

Nom yozilsa xaritada nomi bilan (venue) ko'rinadi, yozilmasa oddiy lokatsiya bo'ladi.
Ikkalasi ham ixtiyoriy — kiritilmasa o'sha xabar yuborilmaydi. 🗑 tugmasi bilan o'chiriladi.

### Yangi admin qo'shish

Ikki yo'l bor:

**1. Odam o'zi ariza yuboradi**
```
Odam /admin yozadi → «📨 Ariza yuborish» → super adminlarga xabar boradi
→ super admin ✅ bosadi → odam «Siz admin etib tayinlandingiz» xabarini oladi
```

**2. Super admin o'zi qo'shadi**
```
👮 Adminlar → ➕ Admin qo'shish → Telegram ID ni yuboradi
Namuna: 123456789 Aliyev Alisher
```

«👮 Adminlar» bo'limida har bir admin uchun: ✅ tasdiqlash · ❌ rad etish ·
👮/👑 rolni almashtirish · 🚫 adminlikdan olish. Tasdiq kutayotganlar soni
tugmada ko'rinadi: `👮 Adminlar (2)`.

---

## Loyiha tuzilishi

```
Dockerfile           bot image'i
docker-compose.yml   bot + PostgreSQL + kunlik zaxira nusxa
deploy/
  DEPLOY.md          serverga chiqarish qo'llanmasi
  server-setup.sh    serverni tayyorlash (bir marta)
  deploy.sh          yuklash / yangilash (kompyuterda ishga tushiriladi)
  remote.sh          serverda ishlaydi (deploy.sh chaqiradi)
bot/
  main.py            ishga tushirish
  config.py          .env dan sozlamalar
  texts.py           BARCHA matnlar shu yerda
  states.py          FSM holatlari
  callbacks.py       inline tugmalar callback data
  db/
    models.py        users / arizalar / fanlar / adminlar / sozlamalar
    seed.py          fanlar ro'yxati
  handlers/
    registration.py  7 qadamli ro'yxatdan o'tish
    menu.py          asosiy menyu
    admin.py         admin panel + admin bo'lishga ariza
  keyboards/         tugmalar
  services/
    arizalar.py      arizalar va fanlar
    adminlar.py      rollar, ruxsatlar, admin tasdiqlash
    stats.py         kunlik / haftalik / oylik statistika
    export.py        Excel (davr bo'yicha filtr bilan)
  middlewares/       DB sessiya, flood himoyasi
  utils/             validatsiya, vaqt (Toshkent)
tests/               soxta Telegram sessiyasi bilan testlar
docs/                spetsifikatsiya
```

**Matnni o'zgartirish** uchun faqat `bot/texts.py` ni tahrirlang.
**Fanlarni o'zgartirish** uchun `bot/db/seed.py` dagi `FANLAR` ro'yxatini tahrirlang.
Ro'yxatdan chiqarilgan fan bazadan o'chmaydi — yashiriladi (`faol = False`),
shuning uchun unga yozilgan eski arizalar saqlanib qoladi.

**Sinflarni o'zgartirish** uchun `bot/keyboards/common.py` dagi `SINFLAR` ni tahrirlang.

Vaqt bazada UTC da saqlanadi, ko'rsatilganda Toshkent vaqtiga o'tkaziladi
(`bot/utils/vaqt.py`) — Excel'dagi sanalar to'g'ri chiqishi uchun.

---

## Keyingi bosqichda qo'shilishi mumkin

- Onlayn test moduli (savollar, timer, avto-baholash)
- Oflayn imtihon markazi + QR kod bilan check-in
- Avtomatik sertifikat (PDF)
- Natijalarni botda e'lon qilish
- Baza sxemasi o'zgarsa — Alembic migratsiyalari
- FSM ni Redis'da saqlash (bot qayta ishga tushganda yarim to'ldirilgan anketa yo'qolmaydi)

> `arizalar` jadvalida bular uchun joy tayyorlangan — sxemani qayta qurish shart bo'lmaydi.
