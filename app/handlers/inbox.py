import logging

from aiogram import Bot, F, Router
from aiogram.types import Message

from app import db
from app.config import settings

logger = logging.getLogger(__name__)

router = Router()

ACK_TEXT = "✅ Ваше сообщение передано. Ответ придёт здесь, в боте."


def _is_admin(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id == settings.admin_telegram_id
    )


@router.message(F.chat.type == "private", F.reply_to_message)
async def admin_reply(message: Message, bot: Bot) -> None:
    if not _is_admin(message) or message.reply_to_message is None:
        return
    user_id = await db.get_inbox_user(message.reply_to_message.message_id)
    if user_id is None:
        return
    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("✅ Ответ отправлен пользователю.")
    except Exception as exc:
        logger.warning("Admin reply to %s failed: %s", user_id, exc)
        await message.answer(
            "⚠️ Не удалось доставить ответ — возможно, пользователь заблокировал бота."
        )


@router.message(F.chat.type == "private")
async def forward_to_admin(message: Message, bot: Bot) -> None:
    if message.from_user is None or _is_admin(message):
        return
    user = message.from_user
    await db.save_user_message(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
        content_type=message.content_type,
        text=message.text or message.caption,
        message_id=message.message_id,
    )
    username = f"@{user.username}" if user.username else "без username"
    header = (
        f"✉️ Сообщение от {user.full_name} ({username}, id <code>{user.id}</code>).\n"
        "Ответьте на это сообщение реплаем — ответ уйдёт пользователю."
    )
    try:
        header_msg = await bot.send_message(settings.admin_telegram_id, header)
        copy = await bot.copy_message(
            chat_id=settings.admin_telegram_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await db.map_admin_message(header_msg.message_id, user.id)
        await db.map_admin_message(copy.message_id, user.id)
        await message.answer(ACK_TEXT)
    except Exception:
        logger.exception("Failed to forward message %s from %s", message.message_id, user.id)
