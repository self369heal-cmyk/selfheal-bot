#!/bin/bash
# Проверка https://bot.selfheal369.ru/health раз в 2 минуты (таймер).
# Алерт об упадении — один раз, о восстановлении — один раз.
set -u
DIR=/opt/bots/selfheal-bot
STATE=/run/selfheal-bot-down
URL=https://bot.selfheal369.ru/health
TS=$(date "+%Y-%m-%d %H:%M UTC")
if curl -sf -m 10 "$URL" >/dev/null; then
  if [ -f "$STATE" ]; then
    rm -f "$STATE"
    "$DIR/notify.sh" "✅ selfheal-bot восстановился ($TS)"
  fi
else
  if [ ! -f "$STATE" ]; then
    touch "$STATE"
    "$DIR/notify.sh" "🔴 selfheal-bot недоступен ($TS): $URL не отвечает. Проверьте systemctl status selfheal-bot на VPS."
  fi
fi
