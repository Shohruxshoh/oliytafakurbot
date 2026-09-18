#!/usr/bin/env bash
# SERVERDA ishlaydi — deploy.sh chaqiradi, qo'lda ishga tushirish shart emas.
#
# Yuklangan fayllar: /opt/oliytafakkurbot/.yuklash/
#   - kod           -> /opt/oliytafakkurbot/ ga ko'chiriladi
#   - .env          -> faqat serverda .env bo'lmasa o'rnatiladi
#   - dump.sql      -> (ixtiyoriy) faqat serverdagi baza bo'sh bo'lsa tiklanadi
set -euo pipefail

MANZIL="${MANZIL:-/opt/oliytafakkurbot}"
YUKLASH="$MANZIL/.yuklash"

# Vaqtinchalik fayllarda .env va baza nusxasi bor — har qanday holatda o'chiriladi
trap 'rm -rf "$YUKLASH"' EXIT

cd "$MANZIL"

env_qiymati() {
  { grep -E "^$1=" .env || true; } | head -n 1 | cut -d= -f2- | tr -d '\r'
}

# ---------------------------------------------------------------- kod
echo "==> [server] Kod yangilanmoqda"
for yol in "$YUKLASH"/* "$YUKLASH"/.dockerignore "$YUKLASH"/.env.example; do
  [ -e "$yol" ] || continue
  nom="$(basename "$yol")"
  if [ "$nom" = "dump.sql" ]; then
    continue
  fi
  rm -rf "./$nom"
  cp -a "$yol" "./$nom"
done
mkdir -p backups

# ---------------------------------------------------------------- .env
if [ -f .env ]; then
  echo "    .env serverda bor — o'zgartirilmadi"
else
  cp "$YUKLASH/.env" .env
  echo "    .env o'rnatildi (birinchi marta)"
fi
sed -i 's/\r$//' .env
chmod 600 .env

if [ "$(env_qiymati POSTGRES_PASSWORD)" = "parolni-ozgartiring" ]; then
  echo "    ⚠️  POSTGRES_PASSWORD standart qiymatda — .env da o'zgartirish tavsiya etiladi"
fi

# ---------------------------------------------------------------- baza ko'chirish
if [ -f "$YUKLASH/dump.sql" ]; then
  echo "==> [server] Baza ko'chirilmoqda"
  PGU="$(env_qiymati POSTGRES_USER)"
  PGD="$(env_qiymati POSTGRES_DB)"
  PGU="${PGU:-olimpiada}"
  PGD="${PGD:-olimpiada}"

  docker compose up -d --wait db

  SONI="$(docker compose exec -T db psql -U "$PGU" -d "$PGD" -tAc 'SELECT count(*) FROM users' 2>/dev/null | tr -d '[:space:]' || true)"
  if [ -n "$SONI" ] && [ "$SONI" != "0" ]; then
    echo "XATO: serverdagi bazada allaqachon $SONI ta o'quvchi bor."
    echo "      Ma'lumot yo'qolmasligi uchun ustidan yozilmadi. Kodni yangilash uchun --baza siz ishga tushiring."
    exit 1
  fi

  docker compose exec -T db psql -v ON_ERROR_STOP=1 -q -U "$PGU" -d "$PGD" \
    < "$YUKLASH/dump.sql" > /dev/null
  SONI="$(docker compose exec -T db psql -U "$PGU" -d "$PGD" -tAc 'SELECT count(*) FROM users' | tr -d '[:space:]')"
  echo "    ko'chirildi: $SONI ta o'quvchi"
fi

# ---------------------------------------------------------------- ishga tushirish
echo "==> [server] Image yig'ilmoqda va ishga tushirilmoqda (birinchi marta 1-3 daqiqa)"
docker compose up -d --build --remove-orphans

ISHLAYAPTI=0
for _ in $(seq 1 40); do
  if docker compose logs bot 2>/dev/null | grep -q "Start polling"; then
    ISHLAYAPTI=1
    break
  fi
  sleep 1
done

echo
docker compose ps
echo
docker compose logs --tail=8 bot
echo

if [ "$ISHLAYAPTI" -eq 1 ]; then
  echo "✅ Bot serverda ishlayapti"
else
  echo "⚠️  Bot hali ishga tushmadi — yuqoridagi loglarni tekshiring"
  exit 1
fi
