---
name: testing-telegram-webhook-bot
description: How to end-to-end test the SelfHeal Telegram bot (aiogram 3 webhooks-only) locally — tunnel, env vars, simulated updates, and what can/can't be verified without a real Telegram user.
---

# Testing the SelfHeal Telegram bot (webhook path)

The app (FastAPI + aiogram 3, `uvicorn app.main:app --port 8000`) registers a Telegram webhook on startup — it never polls, so a public HTTPS URL is required for real Telegram delivery.

## Devin Secrets Needed
- `BOT_TOKEN` — Telegram bot token (provision via session/org secrets). Do NOT write it to files; bind via exec `env` or read it hidden (`read -s BOT_TOKEN; export BOT_TOKEN`).

## Setup
1. `.venv` exists at repo root; deps already installed (`requirements.txt`).
2. Download cloudflared if absent: `curl -sL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x /tmp/cloudflared`.
3. Start a quick tunnel: `/tmp/cloudflared tunnel --url http://localhost:8000 --no-autoupdate` → grab the `https://*.trycloudflare.com` URL from its log.
4. Start the app with `BOT_TOKEN` and `WEBHOOK_BASE_URL=<tunnel URL>` env vars (or a `.env`; config also reads `.env` via pydantic-settings).
5. Verify: `curl "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"` shows the tunnel URL + `/webhooks/telegram`, `pending_update_count` small/zero, no `last_error_message`.

## Endpoints
- `POST /webhooks/telegram` — feeds Update JSON to aiogram Dispatcher.
- `POST /webhooks/getcourse` — stub, logs JSON or form payload, returns `{"status":"ok"}`.
- `GET /health`.

## Key testing knowledge
- Simulating a `/start` update works end-to-end through the tunnel URL: POST a Telegram Update JSON (`message.from.id`, `chat.id`, `text:"/start"`, `entities:[{"type":"bot_command","offset":0,"length":6}]`).
- The handler writes the user row to `selfheal.db` (SQLite) BEFORE calling `message.answer`. With a made-up telegram_id, sendMessage fails (`Bad Request: chat not found` / Forbidden) and propagates → webhook returns HTTP 500, but the DB row exists. Verify the DB write as the pass criterion and record the HTTP status honestly.
- `/start ref_N` stores `referrer_id=N` in the users row; repeated `/start` doesn't duplicate (users.telegram_id is PRIMARY KEY).
- Inspect DB without sqlite3 CLI: `python3 -c "import sqlite3; [print(r) for r in sqlite3.connect('selfheal.db').execute('SELECT * FROM users')]"`.
- For a full real-user check, get the username via `getMe`, ask the user to send /start, and poll the users table for a new telegram_id. A real delivery shows `POST /webhooks/telegram ... 200 OK` and `Update id=N is handled` in uvicorn logs.
- Known quirk to report, not fix during testing: aiogram handler exceptions propagate out of `dp.feed_update`, so any Telegram API error (user blocked bot, bad chat) surfaces as HTTP 500 and Telegram will retry the update.
