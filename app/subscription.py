import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings
from app.keyboards import BACK_LABEL

logger = logging.getLogger(__name__)

SUBSCRIBE_TEXT = (
    "Чтобы получить трек, <b>подпишитесь на канал</b> {channel} 🌿\n\n"
    "Там много полезного (практики, эфиры и анонсы).\n\n"
    "После подписки вернитесь сюда и нажмите «Проверить подписку»."
)


def subscribe_kb(track_id: int, kind: str) -> InlineKeyboardMarkup:
    channel = settings.channel_username.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на канал",
                    url=f"https://t.me/{channel}",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data=f"checksub:{kind}:{track_id}",
                    style="success",
                )
            ],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data="catalog")],
        ]
    )


async def is_subscribed(bot, user_id: int) -> bool | None:
    """True — подписан; False — нет; None — проверка недоступна (бот не админ канала и т.п.)."""
    try:
        member = await bot.get_chat_member(settings.channel_username, user_id)
    except TelegramBadRequest as exc:
        msg = str(exc).lower()
        if "user not found" in msg or "participant_id_invalid" in msg:
            return False
        logger.warning("getChatMember error for %s: %s", user_id, exc)
        return None
    except TelegramAPIError:
        logger.exception("getChatMember failed for %s", user_id)
        return None
    status = getattr(member, "status", "")
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return status in ("creator", "administrator", "member")


async def require_subscription(callback, track_id: int, kind: str) -> bool:
    """False — выдачу остановить (показан экран подписки или алерт об ошибке)."""
    sub = await is_subscribed(callback.bot, callback.from_user.id)
    if sub is True:
        return True
    if sub is None:
        await callback.answer(
            "Проверка подписки временно недоступна. Попробуйте позже 🙌",
            show_alert=True,
        )
    else:
        await callback.message.edit_text(
            SUBSCRIBE_TEXT.format(channel=settings.channel_username),
            reply_markup=subscribe_kb(track_id, kind),
        )
    return False
