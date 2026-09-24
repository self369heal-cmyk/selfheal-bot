import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings

logger = logging.getLogger(__name__)

router = Router()

HELP_TEXT = (
    "Отправьте в этот чат аудио или файл с треком — "
    "я отвечу его file_id для записи в таблицу tracks."
)


def _is_admin(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id == settings.admin_telegram_id
    )


@router.message(Command("getfileid"))
async def cmd_getfileid(message: Message) -> None:
    if not _is_admin(message):
        return
    await message.answer(HELP_TEXT)


@router.message(F.audio | F.document)
async def send_file_id(message: Message) -> None:
    if not _is_admin(message):
        return
    attachment = message.audio or message.document
    await message.answer(f"file_id:\n<code>{attachment.file_id}</code>")
    logger.info(
        "Admin %s requested file_id for %s: %s",
        message.from_user.id,
        getattr(attachment, "file_name", None) or "audio",
        attachment.file_id,
    )
