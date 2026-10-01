from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id     INTEGER PRIMARY KEY,
    referrer_id     INTEGER,
    registered_at   TEXT NOT NULL,
    got_free_track  INTEGER NOT NULL DEFAULT 0,
    bonus_claimed   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    section     TEXT NOT NULL,
    description TEXT,
    file_id     TEXT
);

CREATE TABLE IF NOT EXISTS user_tracks (
    user_id     INTEGER NOT NULL,
    track_id    INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    PRIMARY KEY (user_id, track_id)
);

CREATE TABLE IF NOT EXISTS referrals (
    referrer_id      INTEGER NOT NULL,
    referred_id      INTEGER NOT NULL PRIMARY KEY,
    created_at       TEXT NOT NULL,
    source_track_id  INTEGER
);

CREATE TABLE IF NOT EXISTS user_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    username      TEXT,
    full_name     TEXT,
    content_type  TEXT,
    text          TEXT,
    message_id    INTEGER,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbox_map (
    admin_message_id INTEGER PRIMARY KEY,
    user_telegram_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_number   TEXT PRIMARY KEY,
    telegram_id    INTEGER NOT NULL,
    track_id       INTEGER,
    offer_id       INTEGER,
    amount_rub     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    paid_at        TEXT,
    product_title  TEXT,
    customer_name  TEXT,
    customer_email TEXT,
    customer_phone TEXT,
    paid_notified  INTEGER NOT NULL DEFAULT 0,
    is_test        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_meditations (
    user_id     INTEGER NOT NULL,
    med_id      INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    PRIMARY KEY (user_id, med_id)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    code       TEXT PRIMARY KEY,
    max_uses   INTEGER,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_uses (
    user_id INTEGER NOT NULL,
    code    TEXT NOT NULL,
    used_at TEXT NOT NULL,
    PRIMARY KEY (user_id, code)
);
"""


def _connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.database_path)


# (track_id, title, section, description, file_id) — тексты и файлы утверждены заказчиком.
# description = caption аудио: первая строка — эмодзи + короткое название, дальше тело.
TRACKS_SEED: list[tuple[int, str, str, str, str]] = [
    (1, "АнтиСтресс и расслабление (Покой и гармонизация нервной системы)", "emotions",
     "😊 АнтиСтресс и расслабление\n\n"
     "Этот КИТ <b>снимает стрессовые состояния</b> и психоэмоциональные переживания, "
     "накопленные в теле.\n\n"
     "Дарит глубокое расслабление и покой, улучшает общее самочувствие.\n\n"
     "Убирает резкие эмоциональные всплески, <b>расслабляет нервную и гормональную систему</b>.",
     "CQACAgIAAxkBAAMJarkAAdlWYB6rArRJJCs85YaflDMDAALXpAACecfISU9sn8q2tnFbPQQ"),
    (2, "Устранение любых негативных эмоций (Обиды, страхи, тревожность, истерика у женщин и детей)", "emotions",
     "😭 Устранение любых негативных эмоций\n\n"
     "Этот КИТ помогает <b>растворить любые негативные эмоции</b>: обиды, страхи, тревожность, "
     "истерики.\n\n"
     "Слушайте от 4 минут — чем дольше, тем глубже растворяются эмоции.\n\n"
     "Желательно чётко осознавать, какую эмоцию хотите отпустить, но <b>не фокусироваться на ней "
     "навязчиво</b> — она сама постепенно уйдёт.",
     "CQACAgIAAxkBAAMLarkBHJ6FA2QSAAFeudZVEUklgr5DAALbpAACecfISaoxsEPh8qLePQQ"),
    (3, "Для хорошего сна и быстрого засыпания (От бессонницы)", "emotions",
     "😴 Для хорошего сна и быстрого засыпания\n\n"
     "Этот КИТ помогает <b>легко и быстро уснуть</b>.\n\n"
     "Включите и слушайте, пока не заснёте — "
     "можно один раз, а можно оставить на всю ночь.\n\n"
     "Улучшает засыпание и качество сна. 💤",
     "CQACAgIAAxkBAAMNarkBeqd5pOsXDyT9Rpnb40PNmdcAAuCkAAJ5x8hJFVkvJZkLUDc9BA"),
    (4, "Хорошее настроение, радость и активность", "emotions",
     "🤗 Хорошее настроение, радость и активность\n\n"
     "Этот КИТ <b>улучшает самочувствие</b> и синхронизирует работу гормональной системы — "
     "гипофиз, щитовидную железу, надпочечники, репродуктивную систему.\n\n"
     "Дарит <b>ясность, бодрость и активность</b>, улучшает работу мозга и нервной системы. 🌞",
     "CQACAgIAAxkBAAMParkByyS1OVWUgFBW8taHv6Q80nYAAuOkAAJ5x8hJa-HNSi4sQv89BA"),
    (5, "Концентрация, активация и продуктивность", "energy",
     "🥇 Концентрация, активация и продуктивность\n\n"
     "Этот КИТ <b>активирует внутренние ресурсы</b>, включает мотивацию, вдохновение и желание "
     "творить и действовать.\n\n"
     "Помогает услышать себя и свою миссию.\n\n"
     "Усиливает <b>концентрацию и уверенность в себе</b>, даёт ясность. 🎯",
     "CQACAgIAAxkBAAMRarkCRRfDC1XY625l3mh3dqlR2FAAAuqkAAJ5x8hJQhviK2If5_09BA"),
    (6, "Энергичность, активация силы и бодрости", "energy",
     "⚡ Энергичность, активация силы и бодрость\n\n"
     "Этот КИТ <b>включает состояние энергичности</b>, активирует силы и бодрость, разогревает "
     "мышцы и ресурсы тела.\n\n"
     "Отлично подходит <b>для спорта, тренировок и активных прогулок</b>. 💪",
     "CQACAgIAAxkBAAMTarkCUQdAXaWCP_4e689kur_RJEAAAuukAAJ5x8hJORFiPo5Edrc9BA"),
    (7, "Деньги, изобилие и материализация", "energy",
     "💰 Деньги, изобилие и материализация\n\n"
     "Этот КИТ <b>усиливает материализацию</b> и помогает войти в состояние изобилия.\n\n"
     "Улучшает отношения с деньгами.\n\n"
     "Включает состояние <b>притяжения денег</b> и заземления. 🌍",
     "CQACAgIAAxkBAAMVarkCWW5XfjVDpm-JziITYoBIpBAAAuykAAJ5x8hJmM_bBj0HzhM9BA"),
    (8, "Усиление связи с Душой и Богом", "energy",
     "🙏 Усиление связи с Душой и Богом\n\n"
     "Этот КИТ усиливает <b>связь с душой и Богом</b>.\n\n"
     "В нём собраны разные медитативные состояния, которые помогают настроиться на свой духовный центр.\n\n"
     "Помогает войти в <b>состояние тишины</b> и божественного потока.",
     "CQACAgIAAxkBAAMXarkCXqFKDhVC6jJT2iOE_Ny61D8AAu2kAAJ5x8hJVKge1Y3NHdU9BA"),
    (9, "Здоровая спина, поясница, шея и позвоночник", "body",
     "💃 Здоровая спина, поясница, шея и позвоночник\n\n"
     "В этот КИТ вшиты <b>коды исцеления для тела</b>: спины, поясницы, шеи, костей, суставов "
     "и всего позвоночника.\n\n"
     "Помогает мочеполовой и репродуктивной системе, расслабляет оболочки спинного и головного "
     "мозга — <b>исцеляет то, что чаще всего болит</b>.",
     "CQACAgIAAxkBAAMZarkCfO5l7CtUCecgxSjv9XW2J2QAAu6kAAJ5x8hJ-c2fXurv4Eg9BA"),
    (10, "Здоровая голова и ясность мышления", "body",
     "🧠 Здоровая голова и ясность мышления\n\n"
     "Этот КИТ <b>убирает головные боли</b> и включает ясность в голове.\n\n"
     "Расслабляет оболочки мозга и улучшает циркуляцию спинномозговой жидкости.\n\n"
     "Добавляет больше <b>тишины и ясности мышления</b>.",
     "CQACAgIAAxkBAAMbarkCfPrjhIU0LFSTB8mMda0ysVsAAu-kAAJ5x8hJTSb1JjwOQLY9BA"),
    (11, "Здоровое пищеварение (ЖКТ)", "body",
     "🍇 Здоровое пищеварение (ЖКТ)\n\n"
     "Этот КИТ <b>улучшает работу органов ЖКТ</b> — кишечника, печени, поджелудочной железы "
     "и желудка.\n\n"
     "Гармонизирует все функции желудочно-кишечного тракта.",
     "CQACAgIAAxkBAAMdarkCgYnLZkpl-rJ9ULnV4lKWz-IAAvCkAAJ5x8hJUswcTRRmAAGnPQQ"),
    (12, "Сильный иммунитет", "body",
     "🛡️ Сильный иммунитет\n\n"
     "Этот КИТ помогает <b>быстрее оздоровиться</b> и включает иммунитет на полную мощность.\n\n"
     "Усиливает <b>защитные функции организма</b>.",
     "CQACAgIAAxkBAAMfarkCgwPdNCwOwJQZURGwH1dHic0AAvGkAAJ5x8hJBq4OrUMCPb89BA"),
]


async def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    async with _connect() as db:
        await db.executescript(SCHEMA)
        cursor = await db.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "file_id" not in columns:
            await db.execute("ALTER TABLE tracks ADD COLUMN file_id TEXT")
        cursor = await db.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in await cursor.fetchall()}
        if "bonus_claimed" not in user_columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN bonus_claimed INTEGER NOT NULL DEFAULT 0"
            )
        if "promo_bonus" not in user_columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN promo_bonus INTEGER NOT NULL DEFAULT 0"
            )
        if "promo_awaiting" not in user_columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN promo_awaiting INTEGER NOT NULL DEFAULT 0"
            )
        if "duration_min" in columns:
            await db.execute("ALTER TABLE tracks DROP COLUMN duration_min")
        cursor = await db.execute("PRAGMA table_info(referrals)")
        referral_columns = {row[1] for row in await cursor.fetchall()}
        if "source_track_id" not in referral_columns:
            await db.execute(
                "ALTER TABLE referrals ADD COLUMN source_track_id INTEGER"
            )
        cursor = await db.execute("PRAGMA table_info(orders)")
        order_columns = {row[1] for row in await cursor.fetchall()}
        for name, decl in (
            ("paid_at", "TEXT"),
            ("product_title", "TEXT"),
            ("customer_name", "TEXT"),
            ("customer_email", "TEXT"),
            ("customer_phone", "TEXT"),
            ("paid_notified", "INTEGER NOT NULL DEFAULT 0"),
            ("is_test", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in order_columns:
                await db.execute(f"ALTER TABLE orders ADD COLUMN {name} {decl}")
        # заказы, записанные до появления события «создан», считаем оплаченными
        await db.execute(
            "UPDATE orders SET paid_at = created_at WHERE paid_at IS NULL"
        )
        # коды, созданные до нормализации кириллицы: приводим хранимое значение
        # к тому же виду, что и ввод пользователя, иначе такой код «исчезает»
        cursor = await db.execute("SELECT code FROM promo_codes")
        for (stored,) in await cursor.fetchall():
            norm = _norm_promo(stored)
            if not norm or norm == stored:
                continue
            await db.execute(
                "UPDATE OR IGNORE promo_codes SET code = ? WHERE code = ?",
                (norm, stored),
            )
            # при коллизии (нормализованный код уже есть) — сливаем счётчик
            await db.execute(
                "UPDATE promo_codes SET used_count = used_count + "
                "(SELECT used_count FROM promo_codes WHERE code = ?) "
                "WHERE code = ? AND EXISTS "
                "(SELECT 1 FROM promo_codes WHERE code = ?)",
                (stored, norm, stored),
            )
            await db.execute(
                "DELETE FROM promo_codes WHERE code = ?", (stored,)
            )
            await db.execute(
                "UPDATE OR IGNORE promo_uses SET code = ? WHERE code = ?",
                (norm, stored),
            )
            await db.execute(
                "DELETE FROM promo_uses WHERE code = ?", (stored,)
            )
        await db.executemany(
            """
            INSERT INTO tracks (track_id, title, section, description, file_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                title = excluded.title,
                section = excluded.section,
                description = excluded.description,
                file_id = excluded.file_id
            """,
            TRACKS_SEED,
        )
        await db.commit()


async def get_user(telegram_id: int) -> aiosqlite.Row | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        return await cursor.fetchone()


async def create_user(telegram_id: int, referrer_id: int | None = None) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, referrer_id, registered_at)
            VALUES (?, ?, ?)
            """,
            (telegram_id, referrer_id, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def get_all_tracks() -> list[aiosqlite.Row]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tracks ORDER BY track_id"
        )
        return await cursor.fetchall()


async def get_tracks_by_section(section: str) -> list[aiosqlite.Row]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tracks WHERE section = ? ORDER BY track_id", (section,)
        )
        return await cursor.fetchall()


async def get_track(track_id: int) -> aiosqlite.Row | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tracks WHERE track_id = ?", (track_id,)
        )
        return await cursor.fetchone()


async def get_track_by_title(title: str) -> aiosqlite.Row | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tracks WHERE title = ?", (title,)
        )
        row = await cursor.fetchone()
        if row is not None:
            return row
        # запасной вариант: название трека может прийти с уточнением/обрезкой
        cursor = await db.execute(
            "SELECT * FROM tracks WHERE title LIKE ? LIMIT 1", (f"{title}%",)
        )
        return await cursor.fetchone()


async def user_has_track(user_id: int, track_id: int) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT 1 FROM user_tracks WHERE user_id = ? AND track_id = ?",
            (user_id, track_id),
        )
        return await cursor.fetchone() is not None


async def get_user_tracks(user_id: int) -> list[aiosqlite.Row]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT t.*, ut.received_at FROM user_tracks ut
            JOIN tracks t ON t.track_id = ut.track_id
            WHERE ut.user_id = ?
            ORDER BY ut.received_at
            """,
            (user_id,),
        )
        return await cursor.fetchall()


async def add_user_track(user_id: int, track_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO user_tracks (user_id, track_id, received_at)
            VALUES (?, ?, ?)
            """,
            (user_id, track_id, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def user_has_meditation(user_id: int, med_id: int) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT 1 FROM user_meditations WHERE user_id = ? AND med_id = ?",
            (user_id, med_id),
        )
        return await cursor.fetchone() is not None


async def add_user_meditation(user_id: int, med_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO user_meditations (user_id, med_id, received_at)
            VALUES (?, ?, ?)
            """,
            (user_id, med_id, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def get_user_meditations(user_id: int) -> list[aiosqlite.Row]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT med_id, received_at FROM user_meditations
            WHERE user_id = ? ORDER BY received_at
            """,
            (user_id,),
        )
        return await cursor.fetchall()


async def mark_got_free_track(telegram_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE users SET got_free_track = 1 WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()


async def add_referral(
    referrer_id: int, referred_id: int, source_track_id: int | None = None
) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id, created_at, source_track_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                referrer_id,
                referred_id,
                datetime.now(timezone.utc).isoformat(),
                source_track_id,
            ),
        )
        await db.commit()


async def save_user_message(
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    content_type: str,
    text: str | None,
    message_id: int,
) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO user_messages
                (telegram_id, username, full_name, content_type, text, message_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                username,
                full_name,
                content_type,
                text,
                message_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()


async def map_admin_message(admin_message_id: int, user_telegram_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            "INSERT OR REPLACE INTO inbox_map (admin_message_id, user_telegram_id) VALUES (?, ?)",
            (admin_message_id, user_telegram_id),
        )
        await db.commit()


async def get_inbox_user(admin_message_id: int) -> int | None:
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT user_telegram_id FROM inbox_map WHERE admin_message_id = ?",
            (admin_message_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def upsert_order_created(
    order_number: str,
    telegram_id: int | None,
    track_id: int | None,
    offer_id: int | None,
    amount_rub: int,
    product_title: str | None,
    customer_name: str | None,
    customer_email: str | None,
    customer_phone: str | None,
) -> bool:
    """Записать событие «заказ создан». False — заказ уже есть (идемпотентность)."""
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT 1 FROM orders WHERE order_number = ?", (order_number,)
        )
        exists = await cursor.fetchone() is not None
        await db.execute(
            """
            INSERT INTO orders
                (order_number, telegram_id, track_id, offer_id, amount_rub,
                 product_title, customer_name, customer_email, customer_phone,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_number) DO UPDATE SET
                telegram_id    = CASE WHEN orders.telegram_id = 0
                                   THEN COALESCE(excluded.telegram_id, 0)
                                   ELSE orders.telegram_id END,
                track_id       = COALESCE(excluded.track_id, orders.track_id),
                offer_id       = COALESCE(excluded.offer_id, orders.offer_id),
                amount_rub     = CASE WHEN excluded.amount_rub > 0
                                   THEN excluded.amount_rub ELSE orders.amount_rub END,
                product_title  = COALESCE(excluded.product_title, orders.product_title),
                customer_name  = COALESCE(excluded.customer_name, orders.customer_name),
                customer_email = COALESCE(excluded.customer_email, orders.customer_email),
                customer_phone = COALESCE(excluded.customer_phone, orders.customer_phone)
            """,
            (
                order_number,
                telegram_id if telegram_id is not None else 0,
                track_id,
                offer_id,
                amount_rub,
                product_title,
                customer_name,
                customer_email,
                customer_phone,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()
        return not exists


async def get_order(order_number: str) -> aiosqlite.Row | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE order_number = ?", (order_number,)
        )
        return await cursor.fetchone()


async def mark_order_paid(
    order_number: str,
    telegram_id: int,
    track_id: int | None,
    offer_id: int | None,
    amount_rub: int,
    product_title: str | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
) -> aiosqlite.Row | None:
    """Отметить заказ оплаченным; возвращает строку заказа (created_at для
    расчёта времени до оплаты)."""
    now = datetime.now(timezone.utc).isoformat()
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO orders
                (order_number, telegram_id, track_id, offer_id, amount_rub,
                 product_title, customer_name, customer_email, customer_phone,
                 created_at, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_number) DO UPDATE SET
                paid_at        = excluded.paid_at,
                telegram_id    = CASE WHEN orders.telegram_id IN (NULL, 0)
                                   THEN excluded.telegram_id ELSE orders.telegram_id END,
                track_id       = COALESCE(excluded.track_id, orders.track_id),
                offer_id       = COALESCE(excluded.offer_id, orders.offer_id),
                amount_rub     = CASE WHEN excluded.amount_rub > 0
                                   THEN excluded.amount_rub ELSE orders.amount_rub END,
                product_title  = COALESCE(excluded.product_title, orders.product_title),
                customer_name  = COALESCE(excluded.customer_name, orders.customer_name),
                customer_email = COALESCE(excluded.customer_email, orders.customer_email),
                customer_phone = COALESCE(excluded.customer_phone, orders.customer_phone)
            """,
            (
                order_number,
                telegram_id,
                track_id,
                offer_id,
                amount_rub,
                product_title,
                customer_name,
                customer_email,
                customer_phone,
                now,
                now,
            ),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE order_number = ?", (order_number,)
        )
        return await cursor.fetchone()


async def try_mark_paid_notified(order_number: str) -> bool:
    """True только при первой отметке — защита от дубля уведомления «оплачен»."""
    async with _connect() as db:
        cursor = await db.execute(
            "UPDATE orders SET paid_notified = 1 "
            "WHERE order_number = ? AND paid_notified = 0",
            (order_number,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def pending_unpaid_orders(older_seconds: int = 3600) -> list[aiosqlite.Row]:
    """Заказы, созданные раньше older_seconds назад и ещё не оплаченные."""
    cutoff = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - older_seconds, timezone.utc
    ).isoformat()
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM orders
            WHERE paid_at IS NULL AND is_test = 0 AND created_at < ?
            ORDER BY created_at
            """,
            (cutoff,),
        )
        return await cursor.fetchall()


async def mark_order_test(order_number: str) -> bool:
    """Пометить заказ тестовым — исключается из выручки и pending-списка."""
    async with _connect() as db:
        cursor = await db.execute(
            "UPDATE orders SET is_test = 1 WHERE order_number = ?", (order_number,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def record_order(
    order_number: str,
    telegram_id: int,
    track_id: int | None,
    offer_id: int | None,
    amount_rub: int,
) -> None:
    await mark_order_paid(order_number, telegram_id, track_id, offer_id, amount_rub)


async def get_stats_overview() -> dict:
    async with _connect() as db:
        async def one(query: str, args: tuple = ()) -> int:
            cursor = await db.execute(query, args)
            row = await cursor.fetchone()
            return row[0] if row else 0

        overview = {
            "users_total": await one("SELECT COUNT(*) FROM users"),
            "free_only": await one(
                """
                SELECT COUNT(*) FROM users u
                WHERE u.got_free_track = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM orders o
                      WHERE o.telegram_id = u.telegram_id
                        AND o.paid_at IS NOT NULL AND o.is_test = 0
                  )
                """
            ),
            "buyers": await one(
                "SELECT COUNT(DISTINCT telegram_id) FROM orders "
                "WHERE paid_at IS NOT NULL AND is_test = 0"
            ),
            "orders_total": await one(
                "SELECT COUNT(*) FROM orders WHERE paid_at IS NOT NULL AND is_test = 0"
            ),
            "revenue_total": await one(
                "SELECT COALESCE(SUM(amount_rub),0) FROM orders "
                "WHERE paid_at IS NOT NULL AND is_test = 0"
            ),
            "referrals_total": await one("SELECT COUNT(*) FROM referrals"),
            "ref_buyers": await one(
                """
                SELECT COUNT(*) FROM referrals r
                WHERE EXISTS (
                    SELECT 1 FROM orders o
                    WHERE o.telegram_id = r.referred_id
                      AND o.paid_at IS NOT NULL AND o.is_test = 0
                )
                """
            ),
            "tracks_issued": await one("SELECT COUNT(*) FROM user_tracks"),
            "purchases_total": await one(
                """
                SELECT COUNT(*) FROM orders
                WHERE (track_id IS NOT NULL OR offer_id IS NOT NULL)
                  AND paid_at IS NOT NULL AND is_test = 0
                """
            ),
            "messages_total": await one("SELECT COUNT(*) FROM user_messages"),
        }
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT t.title, COUNT(o.order_number) AS cnt
            FROM tracks t LEFT JOIN orders o
                ON o.track_id = t.track_id AND o.paid_at IS NOT NULL AND o.is_test = 0
            GROUP BY t.track_id ORDER BY cnt DESC, t.track_id
            """
        )
        rows = await cursor.fetchall()
        overview["top_tracks"] = rows[:3]
        # полный рейтинг по выдаче: треки из user_tracks, медитации из user_meditations
        cursor = await db.execute(
            """
            SELECT t.title, COUNT(ut.track_id) AS cnt
            FROM tracks t LEFT JOIN user_tracks ut ON ut.track_id = t.track_id
            GROUP BY t.track_id ORDER BY cnt DESC, t.track_id
            """
        )
        overview["track_issue_rank"] = await cursor.fetchall()
        cursor = await db.execute(
            "SELECT med_id, COUNT(*) AS cnt FROM user_meditations GROUP BY med_id"
        )
        overview["med_issue_counts"] = {
            r["med_id"]: r["cnt"] for r in await cursor.fetchall()
        }
        # какие треки чаще пересылают: приход по ссылке с параметром _track<id>
        cursor = await db.execute(
            """
            SELECT t.title, COUNT(r.referred_id) AS cnt
            FROM referrals r JOIN tracks t ON t.track_id = r.source_track_id
            GROUP BY r.source_track_id ORDER BY cnt DESC, t.track_id
            """
        )
        overview["track_magnets"] = await cursor.fetchall()
        return overview


async def get_daily_stats(since_iso: str) -> dict:
    async with _connect() as db:
        async def one(query: str, args: tuple = ()) -> int:
            cursor = await db.execute(query, args)
            row = await cursor.fetchone()
            return row[0] if row else 0

        return {
            "new_users": await one(
                "SELECT COUNT(*) FROM users WHERE registered_at >= ?", (since_iso,)
            ),
            "orders": await one(
                "SELECT COUNT(*) FROM orders "
                "WHERE paid_at >= ? AND is_test = 0",
                (since_iso,),
            ),
            "revenue": await one(
                "SELECT COALESCE(SUM(amount_rub),0) FROM orders "
                "WHERE paid_at >= ? AND is_test = 0",
                (since_iso,),
            ),
            "new_referrals": await one(
                "SELECT COUNT(*) FROM referrals WHERE created_at >= ?", (since_iso,)
            ),
            "new_messages": await one(
                "SELECT COUNT(*) FROM user_messages WHERE created_at >= ?", (since_iso,)
            ),
        }


async def count_referrals(referrer_id: int) -> int:
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (referrer_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def increment_bonus_claimed(telegram_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE users SET bonus_claimed = bonus_claimed + 1 WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()


# кириллические буквы → латинские аналоги по начертанию/произношению
_CYR_TO_LAT = str.maketrans("АВЕКМНОРСТУХИ", "ABEKMHOPCTYXI")


def _norm_promo(code: str) -> str:
    return code.strip().upper().translate(_CYR_TO_LAT)


async def set_promo_awaiting(user_id: int, awaiting: bool) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE users SET promo_awaiting = ? WHERE telegram_id = ?",
            (int(awaiting), user_id),
        )
        await db.commit()


async def claim_promo_input(user_id: int) -> bool:
    """Атомарно снять флаг ожидания кода: True — только у первого из
    одновременно пришедших сообщений, остальные не доходят до погашения."""
    async with _connect() as db:
        cursor = await db.execute(
            "UPDATE users SET promo_awaiting = 0 "
            "WHERE telegram_id = ? AND promo_awaiting = 1",
            (user_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def is_promo_awaiting(user_id: int) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT promo_awaiting FROM users WHERE telegram_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row[0])


async def add_promo_code(code: str, max_uses: int | None = None) -> bool:
    """Создать промокод. False — уже существует. max_uses=None = безлимит."""
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO promo_codes (code, max_uses, created_at)
            VALUES (?, ?, ?)
            """,
            (_norm_promo(code), max_uses, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_promo_code(code: str) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            "DELETE FROM promo_codes WHERE code = ?", (_norm_promo(code),)
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_promo_codes() -> list[aiosqlite.Row]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM promo_codes ORDER BY created_at"
        )
        return await cursor.fetchall()


async def use_promo(user_id: int, code: str) -> str:
    """Погасить промокод: +1 к promo_bonus пользователя.
    Возвращает 'ok', 'missing', 'exhausted' или 'already_used'."""
    normalized = _norm_promo(code)
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT used_count, max_uses FROM promo_codes WHERE code = ?",
            (normalized,),
        )
        row = await cursor.fetchone()
        if row is None:
            return "missing"
        cursor = await db.execute(
            "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?",
            (user_id, normalized),
        )
        if await cursor.fetchone() is not None:
            return "already_used"
        if row[1] is not None and row[0] >= row[1]:
            return "exhausted"
        await db.execute(
            "INSERT INTO promo_uses (user_id, code, used_at) VALUES (?, ?, ?)",
            (user_id, normalized, datetime.now(timezone.utc).isoformat()),
        )
        await db.execute(
            "UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?",
            (normalized,),
        )
        await db.execute(
            "UPDATE users SET promo_bonus = promo_bonus + 1 WHERE telegram_id = ?",
            (user_id,),
        )
        await db.commit()
        return "ok"
