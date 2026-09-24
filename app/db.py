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


async def init_db() -> None:
    async with _connect() as db:
        await db.executescript(SCHEMA)
        cursor = await db.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "file_id" not in columns:
            await db.execute("ALTER TABLE tracks ADD COLUMN file_id TEXT")
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
