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
"""


def _connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.database_path)


# (track_id, title, section, description, file_id) — тексты и файлы утверждены заказчиком.
# description = caption аудио: первая строка — эмодзи + короткое название, дальше тело.
TRACKS_SEED: list[tuple[int, str, str, str, str]] = [
    (1, "АнтиСтресс и расслабление (Покой и гармонизация нервной системы)", "emotions",
     "😊 АнтиСтресс и расслабление\n"
     "Этот КИТ <b>снимает стрессовые состояния</b> и психоэмоциональные переживания, "
     "накопленные в теле. Дарит глубокое расслабление и покой, улучшает общее самочувствие.\n"
     "Убирает резкие эмоциональные всплески, <b>расслабляет нервную и гормональную систему</b>.",
     "CQACAgIAAxkBAANjarjsCxL7Gic-m_JvQwrals1E_vQAAlGjAAJDK8lJOmdqCBIU0sA9BA"),
    (2, "Устранение любых негативных эмоций (Обиды, страхи, тревожность, истерика у женщин и детей)", "emotions",
     "😭 Устранение любых негативных эмоций\n"
     "Этот КИТ помогает <b>растворить любые негативные эмоции</b>: обиды, страхи, тревожность, "
     "истерики. Слушайте от 4 минут — чем дольше, тем глубже растворяются эмоции.\n"
     "Желательно чётко осознавать, какую эмоцию хотите отпустить, но <b>не фокусироваться на ней "
     "навязчиво</b> — она сама постепенно уйдёт.",
     "CQACAgIAAxkBAANlarjsglEHX65JfLQ3uF79H3txkHQAAlqjAAJDK8lJrZnUr8AtjsY9BA"),
    (3, "Для хорошего сна и быстрого засыпания (От бессонницы)", "emotions",
     "😴 Для хорошего сна и быстрого засыпания\n"
     "Этот КИТ помогает <b>легко и быстро уснуть</b>. Включите и слушайте, пока не заснёте — "
     "можно один раз, а можно оставить на всю ночь. Улучшает засыпание и качество сна. 💤",
     "CQACAgIAAxkBAANnarjsyN6PEklbaKvHCEDChLjqV7EAAl-jAAJDK8lJ0VvrMj6UtWs9BA"),
    (4, "Хорошее настроение, радость и активность", "emotions",
     "🤗 Хорошее настроение, радость и активность\n"
     "Этот КИТ <b>улучшает самочувствие</b> и синхронизирует работу гормональной системы — "
     "гипофиз, щитовидную железу, надпочечники, репродуктивную систему.\n"
     "Дарит <b>ясность, бодрость и активность</b>, улучшает работу мозга и нервной системы. 🌞",
     "CQACAgIAAxkBAANparjs8vbwlvXHDehSHD9JiyZIuH4AAmejAAJDK8lJ_YYTDqh4Grg9BA"),
    (5, "Концентрация, активация и продуктивность", "energy",
     "🥇 Концентрация, активация и продуктивность\n"
     "Этот КИТ <b>активирует внутренние ресурсы</b>, включает мотивацию, вдохновение и желание "
     "творить и действовать. Помогает услышать себя и свою миссию.\n"
     "Усиливает <b>концентрацию и уверенность в себе</b>, даёт ясность. 🎯",
     "CQACAgIAAxkBAANrarjtHaDuQR66eshguAoklH9J9CYAAm-jAAJDK8lJ8oAtbsQwnP09BA"),
    (6, "Энергичность, активация силы и бодрости", "energy",
     "⚡ Энергичность, активация силы и бодрости\n"
     "Этот КИТ <b>включает состояние энергичности</b>, активирует силы и бодрость, разогревает "
     "мышцы и ресурсы тела.\n"
     "Отлично подходит <b>для спорта, тренировок и активных прогулок</b>. 💪",
     "CQACAgIAAxkBAANtarjtPlQsZjkP-ftOR6Q0-rZOJKsAAnOjAAJDK8lJsiddcQ8E6Vk9BA"),
    (7, "Деньги, изобилие и материализация", "energy",
     "💰 Деньги, изобилие и материализация\n"
     "Этот КИТ <b>усиливает материализацию</b> и помогает войти в состояние изобилия. "
     "Улучшает отношения с деньгами.\n"
     "Включает состояние <b>притяжения денег</b> и заземления. 🌍",
     "CQACAgIAAxkBAANvarjtYQ568GEwLUrQKnEKvJ_GMFsAAnSjAAJDK8lJMHZp5EWwxDI9BA"),
    (8, "Усиление связи с Душой и Богом", "energy",
     "🙏 Усиление связи с Душой и Богом\n"
     "Этот КИТ усиливает <b>связь с душой и Богом</b>. В нём собраны разные медитативные "
     "состояния, которые помогают настроиться на свой духовный центр.\n"
     "Помогает войти в <b>состояние тишины</b> и божественного потока.",
     "CQACAgIAAxkBAANxarjthXvkjqvyw_TqLrF_0LQ1r0gAAnajAAJDK8lJRzpnKWgUquc9BA"),
    (9, "Здоровая спина, поясница, шея и позвоночник", "body",
     "💃 Здоровая спина, поясница, шея и позвоночник\n"
     "В этот КИТ вшиты <b>коды исцеления для тела</b>: спины, поясницы, шеи, костей, суставов "
     "и всего позвоночника.\n"
     "Помогает мочеполовой и репродуктивной системе, расслабляет оболочки спинного и головного "
     "мозга — <b>исцеляет то, что чаще всего болит</b>.",
     "CQACAgIAAxkBAANzarjttfeKznGaiYLu0-M0zv7N2AYAAnmjAAJDK8lJXDGSAV9DyXE9BA"),
    (10, "Здоровая голова и ясность мышления", "body",
     "🧠 Здоровая голова и ясность мышления\n"
     "Этот КИТ <b>убирает головные боли</b> и включает ясность в голове. Расслабляет оболочки "
     "мозга и улучшает циркуляцию спинномозговой жидкости.\n"
     "Добавляет больше <b>тишины и ясности мышления</b>.",
     "CQACAgIAAxkBAAN1arjt1JrE_b-XVqLJLT7UI6u7ZJ0AAnyjAAJDK8lJ3oCS7Ld6tPI9BA"),
    (11, "Здоровое пищеварение (ЖКТ)", "body",
     "🍇 Здоровое пищеварение (ЖКТ)\n"
     "Этот КИТ <b>улучшает работу органов ЖКТ</b> — кишечника, печени, поджелудочной железы "
     "и желудка.\n"
     "Гармонизирует все функции желудочно-кишечного тракта.",
     "CQACAgIAAxkBAAN3arjt_EeCc5zBSwABWUG-UQMURBaAAAKAowACQyvJSccq45m5lJcuPQQ"),
    (12, "Сильный иммунитет", "body",
     "🛡️ Сильный иммунитет\n"
     "Этот КИТ помогает <b>быстрее оздоровиться</b> и включает иммунитет на полную мощность.\n"
     "Усиливает <b>защитные функции организма</b>.",
     "CQACAgIAAxkBAAN5arjuEjM_Pr_WHIEb6Wcu4BV-x8IAAoKjAAJDK8lJyHwjUz_ud209BA"),
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
        if "duration_min" in columns:
            await db.execute("ALTER TABLE tracks DROP COLUMN duration_min")
        cursor = await db.execute("PRAGMA table_info(referrals)")
        referral_columns = {row[1] for row in await cursor.fetchall()}
        if "source_track_id" not in referral_columns:
            await db.execute(
                "ALTER TABLE referrals ADD COLUMN source_track_id INTEGER"
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
