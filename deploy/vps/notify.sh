#!/bin/bash
# Отправка алерта админу в Telegram через Worker-релей (VPS не достаёт до api.telegram.org напрямую)
# Использование: notify.sh "текст сообщения"
set -u
DIR=/opt/bots/selfheal-bot
TOKEN=$(grep ^BOT_TOKEN "$DIR/.env" | cut -d= -f2-)
ADMIN=$(grep ^ADMIN_TELEGRAM_ID "$DIR/.env" | cut -d= -f2-)
BASE=$(grep ^TELEGRAM_API_BASE "$DIR/.env" | cut -d= -f2-)
BASE=${BASE:-https://api.telegram.org}
MSG=$1
curl -sf -m 20 -X POST "$BASE/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\":${ADMIN},\"text\":\"${MSG}\"}" >/dev/null
