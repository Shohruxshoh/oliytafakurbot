#!/usr/bin/env bash
# Yangi serverni tayyorlash — BIR MARTA ishga tushiriladi.
# Ubuntu 22.04 / 24.04 yoki Debian 12 uchun.
#
# Kompyuterdan (Git Bash'da):
#   ssh root@SERVER_IP 'bash -s' < deploy/server-setup.sh
#
# root bo'lmagan foydalanuvchi bilan:
#   ssh user@SERVER_IP 'sudo bash -s' < deploy/server-setup.sh
set -euo pipefail

MANZIL=/opt/oliytafakkurbot

if [ "$(id -u)" -ne 0 ]; then
  echo "XATO: root huquqi kerak. 'sudo bash -s' bilan ishga tushiring."
  exit 1
fi

# Skript 'bash -s' orqali stdin'dan o'qiladi — shuning uchun hech bir buyruq
# stdin'ni o'qimasligi kerak (< /dev/null), aks holda skriptning qolgan qismini "yeb qo'yadi".
echo "==> Paketlar yangilanmoqda"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q < /dev/null
apt-get install -y -q ca-certificates curl < /dev/null

if command -v docker >/dev/null 2>&1; then
  echo "==> Docker allaqachon o'rnatilgan"
else
  echo "==> Docker o'rnatilmoqda (rasmiy skript: get.docker.com)"
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh < /dev/null
  rm -f /tmp/get-docker.sh
fi
systemctl enable --now docker >/dev/null

# Server qayta yuklanganda Docker va bot o'zi ishga tushadi (restart: unless-stopped)

EGA="${SUDO_USER:-root}"
mkdir -p "$MANZIL"
chown "$EGA":"$EGA" "$MANZIL"
if [ "$EGA" != "root" ]; then
  usermod -aG docker "$EGA"
  echo "==> $EGA docker guruhiga qo'shildi (keyingi SSH ulanishda kuchga kiradi)"
fi

echo
echo "==> Tayyor"
docker --version
docker compose version
echo "Bot papkasi: $MANZIL"
