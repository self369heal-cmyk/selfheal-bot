import logging
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
    await message.answer_document(
        FSInputFile(db_path, filename=f"selfheal_{stamp}.db"),
        caption="Резервная копия базы selfheal.db",
    )
    logger.info("DB backup sent to admin %s", message.from_user.id)
