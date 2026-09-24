from datetime import datetime, timezone

import aiosqlite

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id     INTEGER PRIMARY KEY,
    referrer_id     INTEGER,
    registered_at   TEXT NOT NULL,
    got_free_track  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    section     TEXT NOT NULL,
    duration_min INTEGER,
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
    referrer_id INTEGER NOT NULL,
    referred_id INTEGER NOT NULL PRIMARY KEY,
    created_at  TEXT NOT NULL
);
"""


def _connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.database_path)


# (track_id, title, section, duration_min, description) — раздел 1.3 документа
TRACKS_SEED: list[tuple[int, str, str, int | None, str]] = [
    (1, "АнтиСтресс и расслабление, покой и гармонизация", "emotions", None,
     "Снимает стресс и внутреннее напряжение, возвращает покой и гармоничное состояние."),
    (2, "Устранение любых негативных эмоций (обиды, страхи, тревожность, истерика у женщин и детей)", "emotions", None,
     "Помогает отпустить обиды, страхи и тревожность; работает и с истериками у женщин и детей."),
    (3, "Легкое засыпание и расслабление", "emotions", None,
     "Мягко расслабляет и облегчает засыпание — можно слушать на ночь."),
    (4, "Хорошее настроение и радость", "emotions", None,
     "Поднимает настроение и возвращает ощущение радости и лёгкости."),
    (5, "Концентрация, уверенность и продуктивность", "energy", None,
     "Помогает собраться, усилить концентрацию, уверенность и продуктивность."),
    (6, "Энергичность, активность и бодрость", "energy", None,
     "Наполняет энергией, возвращает активность и бодрость."),
    (7, "Деньги, изобилие, продуктивность и реализация в легкости", "energy", None,
     "Настраивает на состояние изобилия: деньги, реализация и движение вперёд в лёгкости."),
    (8, "Усиление связи с собой, Душой и Богом", "energy", None,
     "Углубляет связь с собой, Душой и Богом."),
    (9, "Здоровая спина, поясница и шея, кости и суставы", "body", None,
     "Работает со спиной, поясницей и шеей; поддерживает кости и суставы."),
    (10, "Здоровая голова и ясность мышления", "body", None,
     "Заботится о здоровье головы и возвращает ясность мышления."),
    (11, "Здоровое пищеварение (ЖКТ)", "body", None,
     "Гармонизирует работу желудочно-кишечного тракта."),
    (12, "Сильный иммунитет", "body", None,
     "Поддерживает и укрепляет иммунитет."),
]


async def init_db() -> None:
    async with _connect() as db:
        await db.executescript(SCHEMA)
        cursor = await db.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "file_id" not in columns:
            await db.execute("ALTER TABLE tracks ADD COLUMN file_id TEXT")
        await db.executemany(
            """
            INSERT OR IGNORE INTO tracks (track_id, title, section, duration_min, description)
            VALUES (?, ?, ?, ?, ?)
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


async def user_has_track(user_id: int, track_id: int) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT 1 FROM user_tracks WHERE user_id = ? AND track_id = ?",
            (user_id, track_id),
        )
        return await cursor.fetchone() is not None


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
