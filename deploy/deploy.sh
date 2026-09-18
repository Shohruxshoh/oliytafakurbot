#!/usr/bin/env bash
# Botni serverga yuklash va ishga tushirish. Windows'da GIT BASH orqali ishga tushiring.
#
#   bash deploy/deploy.sh root@SERVER_IP           kodni yuklash / yangilash
#   bash deploy/deploy.sh root@SERVER_IP --baza    + kompyuterdagi bazani ko'chirish
#                                                  (faqat birinchi marta — serverda baza bo'sh bo'lsa)
#
# Nima qiladi:
#   1. Testlarni ishga tushiradi — o'tmasa, yuklamaydi
#   2. Kompyuterdagi botni to'xtatadi (bitta token bilan ikki joyda ishlab bo'lmaydi)
#   3. Kod + .env (+ baza nusxasi) ni bitta SSH ulanish orqali yuboradi
#   4. Serverda deploy/remote.sh ni ishga tushiradi
#
# .env serverga faqat BIRINCHI marta o'rnatiladi, keyin serverdagisi saqlanadi.
set -euo pipefail

SERVER="${1:-}"
BAZA=0
if [ "${2:-}" = "--baza" ]; then
  BAZA=1
fi

if [ -z "$SERVER" ] || [[ "$SERVER" == -* ]]; then
  echo "Foydalanish: bash deploy/deploy.sh root@SERVER_IP [--baza]"
  exit 1
fi

cd "$(dirname "$0")/.."

MANZIL="${MANZIL:-/opt/oliytafakkurbot}"
YUKLASH="$MANZIL/.yuklash"

if [ ! -f .env ]; then
  echo "XATO: .env topilmadi. .env.example dan nusxa olib to'ldiring."
  exit 1
fi

env_qiymati() {
  { grep -E "^$1=" .env || true; } | head -n 1 | cut -d= -f2- | tr -d '\r'
}

VAQTINCHA="$(mktemp -d)"
LOKAL_TOXTATILDI=0

tugash() {
  local kod=$?
  rm -rf "$VAQTINCHA"
  if [ "$kod" -ne 0 ] && [ "$LOKAL_TOXTATILDI" -eq 1 ]; then
    echo
    echo "Yuklash muvaffaqiyatsiz. Kompyuterdagi botni qayta yoqish uchun:"
    echo "    docker compose start bot"
  fi
}
trap tugash EXIT

# ---------------------------------------------------------------- 1. testlar
PY=""
if [ -x .venv/Scripts/python.exe ]; then
  PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
fi

if [ -n "$PY" ]; then
  echo "==> Testlar"
  for t in smoke e2e_registratsiya e2e_admin; do
    if ! PYTHONIOENCODING=utf-8 "$PY" "tests/$t.py" > "$VAQTINCHA/test.log" 2>&1; then
      tail -n 25 "$VAQTINCHA/test.log"
      echo "XATO: $t testi o'tmadi — serverga yuklanmadi."
      exit 1
    fi
    echo "    $t — o'tdi"
  done
else
  echo "==> .venv topilmadi — testlar o'tkazib yuborildi"
fi

# ---------------------------------------------------------------- 2. lokal bot / baza
LOKAL_DOCKER=0
if docker info >/dev/null 2>&1; then
  LOKAL_DOCKER=1
fi

if [ "$BAZA" -eq 1 ]; then
  if [ "$LOKAL_DOCKER" -eq 0 ]; then
    echo "XATO: --baza uchun Docker Desktop yoqilgan bo'lishi kerak (lokal bazadan nusxa olinadi)."
    exit 1
  fi
  PGU="$(env_qiymati POSTGRES_USER)"
  PGD="$(env_qiymati POSTGRES_DB)"
  PGU="${PGU:-olimpiada}"
  PGD="${PGD:-olimpiada}"

  echo "==> Kompyuterdagi bot to'xtatilmoqda (nusxa olinayotganda yangi yozuv tushmasligi uchun)"
  docker compose stop bot >/dev/null 2>&1 || true
  LOKAL_TOXTATILDI=1

  echo "==> Lokal bazadan nusxa olinmoqda"
  docker compose up -d --wait db >/dev/null
  docker compose exec -T db pg_dump -U "$PGU" -d "$PGD" --clean --if-exists --no-owner \
    > "$VAQTINCHA/dump.sql"
  echo "    hajmi: $(du -h "$VAQTINCHA/dump.sql" | cut -f1)"
elif [ "$LOKAL_DOCKER" -eq 1 ] && [ -n "$(docker compose ps -q bot 2>/dev/null)" ]; then
  echo "==> Kompyuterdagi bot to'xtatilmoqda (serverdagi bot bilan to'qnashmasligi uchun)"
  docker compose stop bot >/dev/null
  LOKAL_TOXTATILDI=1
fi

# ---------------------------------------------------------------- 3-4. yuklash va ishga tushirish
TAR_ARGS=(
  -czf -
  --exclude=./.venv
  --exclude=./.git
  --exclude=./.claude
  --exclude=./.idea
  --exclude=./.vscode
  --exclude=./backups
  --exclude=./data
  --exclude=./eksport
  --exclude='*.db'
  --exclude=__pycache__
  .
)
if [ "$BAZA" -eq 1 ]; then
  TAR_ARGS+=(-C "$VAQTINCHA" dump.sql)
fi

echo "==> Serverga yuklanmoqda: $SERVER"
# Bitta SSH ulanish — parol bilan kirilsa ham faqat bir marta so'raladi.
#   --no-same-owner  : fayllar Windows'dagi uid bilan emas, server foydalanuvchisi nomidan
#   sed 's/\r$//'    : Windows'da tahrirlangan skriptdagi CRLF Linux'da bash'ni buzmasligi uchun
# $YUKLASH ataylab shu yerda (kompyuterda) ochiladi — yo'l ikkala tomonda bir xil.
# shellcheck disable=SC2029
tar "${TAR_ARGS[@]}" | ssh "$SERVER" \
  "set -e; rm -rf '$YUKLASH'; mkdir -p '$YUKLASH'; chmod 700 '$YUKLASH'; tar -xzf - --no-same-owner -C '$YUKLASH'; find '$YUKLASH' -name '*.sh' -exec sed -i 's/\r\$//' {} +; MANZIL='$MANZIL' bash '$YUKLASH/deploy/remote.sh'"

echo
echo "Tayyor. Loglarni kuzatish:"
echo "    ssh $SERVER 'cd $MANZIL && docker compose logs -f bot'"
