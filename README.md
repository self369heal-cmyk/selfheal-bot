# Тайная природа СамоИсцеления — Telegram-бот

Telegram-бот на **aiogram 3** (вебхуки, не polling) + **FastAPI** на том же сервере
для приёма вебхуков от GetCourse. База данных — **SQLite**.

## Структура

```
app/
  main.py            # FastAPI-приложение: lifespan, роуты, регистрация вебхука
  config.py          # Настройки из переменных окружения (.env)
  bot.py             # Фабрики Bot и Dispatcher (aiogram 3)
  db.py              # SQLite: схема и функции доступа (aiosqlite)
  texts.py           # Экранные тексты (дословно из раздела 2 сценария)
  keyboards.py       # Inline-клавиатуры: главное меню, назад, кнопка-ссылка Владемиру
  handlers/start.py  # /start — приветствие и регистрация пользователя
  handlers/getfileid.py  # /getfileid — админская команда, возвращает file_id присланного аудио/файла
  handlers/menu.py   # Inline-меню: разделы «Как слушать КИТ», «Про автора», «Индивидуальный трек», «Индивидуальный сеанс», заглушки остальных
  handlers/catalog.py # Каталог: разделы → список треков → карточка; бесплатный первый трек, ссылка оплаты GetCourse
  handlers/referral.py # Рефералка: экран со ссылкой и счётчиком, бонус-треки за каждые 3 друга
  handlers/purchases.py # «Мои покупки»: список треков + повторная отправка по file_id
  webhooks/telegram.py   # POST /webhooks/telegram — апдейты Telegram → aiogram
  webhooks/getcourse.py  # POST /webhooks/getcourse — заглушка, логирует payload
```

## База данных

| Таблица | Поля |
|---|---|
| users | telegram_id, referrer_id, registered_at, got_free_track, bonus_claimed |
| tracks | track_id, title, section, duration_min, description, file_id |
| user_tracks | user_id, track_id, received_at |
| referrals | referrer_id, referred_id, created_at |

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # впишите BOT_TOKEN и WEBHOOK_BASE_URL
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

При старте приложение создаёт таблицы и, если заданы `BOT_TOKEN` и
`WEBHOOK_BASE_URL`, регистрирует вебхук Telegram на
`{WEBHOOK_BASE_URL}/webhooks/telegram`. Для локальной разработки поднимите
HTTPS-туннель (например, `ngrok http 8000`) и подставьте его адрес в
`WEBHOOK_BASE_URL`.

## Аудиотреки

Треки не хранятся файлами на сервере — в `tracks.file_id` лежит Telegram file_id,
и выдача трека идёт через `sendAudio`/`sendDocument` с этим file_id. Чтобы
получить file_id, администратор (telegram_id в `ADMIN_TELEGRAM_ID`) отправляет
боту команду `/getfileid`, затем присылает аудио или документ — бот отвечает его
file_id.

## Эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| POST | /webhooks/telegram | Приём апдейтов Telegram (передаются в aiogram Dispatcher) |
| POST | /webhooks/getcourse | Вебхук оплаты GetCourse: по telegram_id + названию трека + статусу записывает покупку в `user_tracks` и отправляет файл по `file_id` (sendAudio → запасной sendDocument) |
| GET | /health | Проверка живости сервиса |

## Переменные окружения

См. `.env.example`: `BOT_TOKEN`, `WEBHOOK_BASE_URL`, `WEBAPP_HOST`,
`WEBAPP_PORT`, `DATABASE_PATH`, `ADMIN_TELEGRAM_ID`, `GETCOURSE_PAY_URL_TEMPLATE`.
Пути вебхуков можно переопределить через
`TELEGRAM_WEBHOOK_PATH` и `GETCOURSE_WEBHOOK_PATH`.

## Деплой на сервер (VPS)

1. Склонируйте репозиторий и установите зависимости:
   ```bash
   git clone https://github.com/self369heal-cmyk/selfheal-bot.git && cd selfheal-bot
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Создайте `.env` по образцу `.env.example` и заполните:
   - `BOT_TOKEN` — токен боевого бота от @BotFather
   - `WEBHOOK_BASE_URL` — публичный HTTPS-адрес сервера (домен с SSL — вебхуки Telegram требуют HTTPS; например через nginx + certbot или встроенный TLS у Amvera)
   - `ADMIN_TELEGRAM_ID` — ваш telegram_id (команда /getfileid)
   - `GETCOURSE_PAY_URL_TEMPLATE` — реальный шаблон ссылки оплаты GetCourse
   - опционально `DATABASE_PATH`, `WEBAPP_HOST`, `WEBAPP_PORT`, пути вебхуков
3. Запустите:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   При старте бот сам создаст таблицы, засеет каталог и зарегистрирует вебхук Telegram
   на `{WEBHOOK_BASE_URL}/webhooks/telegram` (удаляет его при остановке).
4. Для автозапуска — systemd-юнит, напр.:
   ```ini
   [Unit]
   Description=SelfHeal Bot
   After=network.target
   [Service]
   WorkingDirectory=/opt/selfheal-bot
   EnvironmentFile=/opt/selfheal-bot/.env
   ExecStart=/opt/selfheal-bot/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always
   [Install]
   WantedBy=multi-user.target
   ```
5. В GetCourse укажите вебхук оплаты: `{WEBHOOK_BASE_URL}/webhooks/getcourse`
   (POST, поля: telegram_id, название трека, статус).

Проверка: `GET /health` → `{"status": "ok"}`.

## Следующие шаги (по сценарию)

Все шаги сценария реализованы.
