---
name: testing-telegram-webhook-bot
description: How to end-to-end test the SelfHeal Telegram bot (aiogram 3 webhooks) — local tunnel runs AND production @SelfHeal_KIT_bot via Cloudflare Worker relay, simulated updates, and Bot-API-based verification tricks.
---

# Testing the SelfHeal Telegram bot (webhook path)

The app (FastAPI + aiogram 3) registers a Telegram webhook on startup — it never polls.

## Devin Secrets Needed
- `BOT_TOKEN` — test bot (@selfheal_test_bot) token for local runs.
- `SelfHeal_KIT_bot_TOKEN` — PROD bot token; also fetchable via `ssh grep ^BOT_TOKEN /opt/bots/selfheal-bot/.env`.
- VPS access: `ssh -i ~/.ssh/selfheal_vps root@194.67.113.21` (code at /opt/bots/selfheal-bot, `journalctl -u selfheal-bot`).

## Two surfaces

### Local run
`.venv` at repo root. Start cloudflared quick tunnel (`/tmp/cloudflared tunnel --url http://localhost:8000`), set `BOT_TOKEN` + `WEBHOOK_BASE_URL=<tunnel>`, run `.venv/bin/uvicorn app.main:app`. Verify `getWebhookInfo`.

### Production @SelfHeal_KIT_bot
- Webhook: `https://bot.selfheal369.ru/webhooks/telegram` (Telegram actually targets the Worker `https://selfheal-tg-proxy.selfheal-tg.workers.dev/webhooks/telegram`, which proxies to origin — see `deploy/cloudflare/worker.js`).
- **Simulated updates**: POST Update JSON to the webhook URL with header `X-Telegram-Bot-Api-Secret-Token` (value = `TELEGRAM_WEBHOOK_SECRET` from VPS .env — fetch via ssh, never print it). Webhook always returns 200 (feed_update wrapped).
- **Bot API calls**: via Worker relay `https://selfheal-tg-proxy.selfheal-tg.workers.dev/bot<TOKEN>/<METHOD>` — sendMessage/sendPhoto/editMessage*/deleteMessage/forwardMessage all work (>50KB uploads don't; media only via file_id from app code).
- Admin chat (tg_id 5925313775, `settings.admin_telegram_id`) is the test ground — every bot send is real and visible to the user.

## Verification primitives (prod)
- **Gap arithmetic** (dup detector): `sendMessage` returns sequential chat ids; `gap = id_after - id_before - 1` = bot messages sent between probes. Edit-in-place → 0; new-screen → +1; author flow → +3. Your own `forwardMessage` copies consume ids too — account for them.
- **file_unique_id equality**: `sendPhoto(file_id)` probe → `photo[-1].file_unique_id` is content-stable; `forwardMessage(msg)` returns the full Message (caption + photo uid) → proves WHICH image a screen shows.
- **Delete verify**: `editMessageReplyMarkup` on a deleted msg → "message to edit not found".
- **Markup-equality probe**: `editMessageReplyMarkup` with the exact expected keyboard JSON → "Bad Request: message is not modified" = keyboard was already exactly that (PASS). If it succeeds, markup differed — still non-destructive if your JSON mirrors the code's keyboard.
- **Force the delete-failure fallback** (PR #33 path): relay `sendMessage`/`sendPhoto` → `deleteMessage` it → simulated callback on that dead message → handler sends new screen, `delete()` fails → `logger.warning("...failed to delete...")` in `journalctl -u selfheal-bot` — proves try/except fires and no retry-dup occurs.
- **Update JSON shape**: callback update needs `callback_query{ id, from{admin}, message{message_id of REAL msg, from{id:8699077910 is_bot:true}, chat{admin private}, date, "photo":[...] if photo msg}, chat_instance, data }`. Message update: `message{message_id, from{admin}, chat, date, text, entities[bot_command]}`. Fake callback ids can't be answered (Telegram QUERY_ID_INVALID → one ERROR log, harmless; webhook still 200).

## Known quirks
- `DEBOUNCE_SECONDS=0.6` middleware drops same-(user,data) callbacks — rapid-fire tests see single handling.
- No read-only "get message" Bot API exists: inspect content via `forwardMessage` (strips kb) or mutating edit probes.
- Admin commands: `/stats`, `/pending_orders` (PR #32 branch may be deployed ahead of merge), `/backupdb`, `/promo*`, `/getfileid`, `/menu`. Admin's own messages aren't inbox-forwarded.
- Don't blanket-`deleteMessage` by id range in admin chat — bots can delete ANY private-chat message including the user's. Delete only ids you created.
