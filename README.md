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
  webhooks/telegram.py   # POST /webhooks/telegram — апдейты Telegram → aiogram
  webhooks/getcourse.py  # POST /webhooks/getcourse — заглушка, логирует payload
```

## База данных

| Таблица | Поля |
|---|---|
| users | telegram_id, referrer_id, registered_at, got_free_track |
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
| POST | /webhooks/getcourse | Заглушка для сигнала оплаты GetCourse — логирует тело запроса (JSON или form-data) |
| GET | /health | Проверка живости сервиса |

## Переменные окружения

См. `.env.example`: `BOT_TOKEN`, `WEBHOOK_BASE_URL`, `WEBAPP_HOST`,
`WEBAPP_PORT`, `DATABASE_PATH`, `ADMIN_TELEGRAM_ID`. Пути вебхуков можно переопределить через
`TELEGRAM_WEBHOOK_PATH` и `GETCOURSE_WEBHOOK_PATH`.

## Следующие шаги (по сценарию)

Каталог из 12 треков с бесплатным первым треком, полная обработка
оплаты GetCourse (выдача .flac), реферальная программа «3 друга = бонус-трек»,
раздел «Мои покупки» и дисклеймер.
