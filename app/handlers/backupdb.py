import asyncio
import gzip
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from app.config import settings

logger = logging.getLogger(__name__)

router = Router()


def _is_admin(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id == settings.admin_telegram_id
    )


def _gzip_db(src: Path, dst: Path) -> None:
    with open(dst, "wb") as out, gzip.GzipFile(fileobj=out, mode="wb") as gz:
        with open(src, "rb") as db_file:
            shutil.copyfileobj(db_file, gz)


@router.message(Command("backupdb"))
async def cmd_backupdb(message: Message) -> None:
    """Присылает админу актуальный файл SQLite-базы документом."""
    if not _is_admin(message):
        return
    db_path = Path(settings.database_path)
    if not db_path.exists():
        await message.answer("Файл базы не найден")
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    # сеть VPS→релей режет большие аплоады — шлём сжато (~1/6 размера)
    tmp_path = Path(tempfile.NamedTemporaryFile(suffix=".gz", delete=False).name)
    try:
        await asyncio.to_thread(_gzip_db, db_path, tmp_path)
        await message.answer_document(
            FSInputFile(tmp_path, filename=f"selfheal_{stamp}.db.gz"),
            caption="Резервная копия базы selfheal.db (gzip)",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    logger.info("DB backup sent to admin %s", message.from_user.id)
