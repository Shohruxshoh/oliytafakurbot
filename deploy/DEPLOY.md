# Botni serverga chiqarish

## Nima kerak

| | |
|---|---|
| **Server** | VPS, Ubuntu 22.04 yoki 24.04. **1 vCPU, 1 GB RAM, 10 GB disk** yetarli |
| **Kompyuterda** | Git Bash (Git for Windows bilan birga keladi) |

- ❌ Oddiy hosting (cPanel, shared hosting) **ishlamaydi** — Docker kerak.
- ✅ Domen, SSL sertifikat, ochiq port **kerak emas**. Bot Telegram'ga o'zi ulanadi
  (polling), serverga tashqaridan hech kim ulanmaydi.
- Server Yevropada bo'lsa yaxshi — Telegram serverlari u yerda, javob tezroq keladi.

Quyidagi barcha buyruqlar **Git Bash**'da, loyiha papkasida bajariladi
(`deploy/`, `bot/`, `docker-compose.yml` turgan papka). GitHub'dan klonlagan bo'lsangiz:

```bash
git clone https://github.com/Shohruxshoh/oliytafakurbot.git
```

```bash
cd oliytafakurbot
```

Klonlagandan keyin `.env` faylini yarating — u GitHub'da **yo'q** (maxfiy):
`.env.example` dan nusxa olib, tokeningiz va parolingizni yozing.

`SERVER_IP` o'rniga serveringiz IP manzilini yozing (masalan `root@95.217.10.20`).

---

## 1-qadam. SSH kalit — bir marta (tavsiya etiladi)

Har safar parol kiritmaslik uchun.

```bash
ssh-keygen -t ed25519
```

Savollarga Enter bosib o'tavering. Keyin kalitni serverga qo'shing (server parolini oxirgi marta so'raydi):

```bash
cat ~/.ssh/id_ed25519.pub | ssh root@SERVER_IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Tekshirish — parol so'ramasa, tayyor:

```bash
ssh root@SERVER_IP "echo ulandi"
```

---

## 2-qadam. Serverni tayyorlash — bir marta

```bash
sed 's/\r$//' deploy/server-setup.sh | ssh root@SERVER_IP 'bash -s'
```

Docker o'rnatiladi va `/opt/oliytafakkurbot` papkasi yaratiladi. 2–3 daqiqa.

---

## 3-qadam. Botni yuklash

**Kompyuterdagi arizalarni ham ko'chirish** (Docker Desktop yoqilgan bo'lishi kerak):

```bash
bash deploy/deploy.sh root@SERVER_IP --baza
```

**Yoki toza baza bilan boshlash:**

```bash
bash deploy/deploy.sh root@SERVER_IP
```

Skript o'zi:

1. Testlarni ishga tushiradi — o'tmasa, **yuklamaydi**
2. Kompyuterdagi botni to'xtatadi
3. Kod va `.env` ni serverga yuboradi
4. Serverda ishga tushiradi va natijani ko'rsatadi

Oxirida shu chiqishi kerak:

```
✅ Bot serverda ishlayapti
```

> `--baza` faqat serverdagi baza **bo'sh** bo'lsa ishlaydi. Serverda allaqachon o'quvchilar
> bo'lsa, skript to'xtaydi — ma'lumot ustidan yozilmaydi.

---

## Kodni yangilash

Kod o'zgargandan keyin — xuddi shu buyruq, `--baza` siz:

```bash
bash deploy/deploy.sh root@SERVER_IP
```

Serverdagi baza, `.env` va zaxira nusxalar saqlanadi. Bot 10–30 soniya to'xtab, qayta ishga tushadi.

---

## ⚠️ Bitta token — bitta bot

Telegram bitta tokenni **faqat bitta joydan** ishlatishga ruxsat beradi. `deploy.sh`
kompyuterdagi botni o'zi to'xtatadi. Agar keyin kompyuterda yana `docker compose up`
qilsangiz, ikkala bot to'qnashadi va loglarda shu xato chiqadi:

```
Conflict: terminated by other getUpdates request
```

Kompyuterda sinab ko'rish uchun [@BotFather](https://t.me/BotFather) dan **alohida test bot**
oching va kompyuterdagi `.env` ga uning tokenini yozing. Serverdagi `.env` ga tegilmaydi.

---

## Serverda boshqaruv

```bash
ssh root@SERVER_IP
```

```bash
cd /opt/oliytafakkurbot
```

| Buyruq | Vazifasi |
|---|---|
| `docker compose logs -f bot` | Loglarni jonli kuzatish (chiqish — Ctrl+C) |
| `docker compose ps` | Holat |
| `docker compose restart bot` | Qayta ishga tushirish |
| `nano .env` | Sozlamalarni o'zgartirish, keyin `docker compose up -d` |

---

## Zaxira nusxalar

Server bazadan **har 24 soatda** avtomatik nusxa oladi:
`/opt/oliytafakkurbot/backups/`, oxirgi **14 kun** saqlanadi.

**Kompyuterga yuklab olish** — haftada bir marta qiling, server ham buzilishi mumkin:

```bash
scp "root@SERVER_IP:/opt/oliytafakkurbot/backups/*.sql.gz" .
```

**Nusxadan tiklash** — ⚠️ hozirgi bazani to'liq almashtiradi. Serverda:

```bash
cd /opt/oliytafakkurbot && docker compose stop bot
```

```bash
gunzip -c backups/FAYL_NOMI.sql.gz | docker compose exec -T db psql -U olimpiada -d olimpiada
```

```bash
docker compose start bot
```

---

## Muammolar

| Belgi | Sabab va yechim |
|---|---|
| `Conflict: terminated by other getUpdates request` | Bot ikki joyda ishlayapti — kompyuterdagini to'xtating: `docker compose stop bot` |
| `BOT_TOKEN noto'g'ri — Telegram qabul qilmadi` | Serverdagi `.env` da token xato — `nano .env` |
| `Permission denied (publickey)` | SSH kalit o'rnatilmagan — 1-qadam |
| `POSTGRES_PASSWORD ... ko-rsatilishi shart` | `.env` da `POSTGRES_PASSWORD` yo'q |
| `--baza uchun Docker Desktop yoqilgan bo'lishi kerak` | Kompyuterda Docker Desktop'ni yoqing |
| `testi o'tmadi — serverga yuklanmadi` | Kodda xato bor — tuzatilmaguncha yuklanmaydi (bu himoya) |
