import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import db
from app.config import settings
from app.keyboards import BACK_LABEL, CB_MENU

logger = logging.getLogger(__name__)

router = Router()

FRIENDS_PER_BONUS = 3

REFERRAL_TEXT = """Приглашайте друзей — получайте треки в подарок 🎁

Пригласите 3 друзей, которые запустят бота по вашей ссылке — и вы получите ещё один трек бонусом, на выбор из каталога.
За каждые следующие 3 приглашённых друга — новый бонус-трек на выбор.

Ваша ссылка: {link}
Приглашено друзей: {count} из {next_milestone}"""

BONUS_NOTIFY_TEXT = (
    "🎉 Отлично! Вы пригласили уже {count} друзей — "
    "у вас открыт бонус: ещё один трек на выбор из каталога 🎁"
)

SUBSCRIBE_TEXT = (
    "Чтобы получить бонусный трек, подпишитесь на наш канал {channel} 🌿\n\n"
    "Там — новые практики, разборы и анонсы.\n"
    "После подписки вернитесь сюда и нажмите «Проверить подписку»."
)


def subscribe_kb(track_id: int) -> InlineKeyboardMarkup:
    channel = settings.channel_username.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на канал",
                    url=f"https://t.me/{channel}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data=f"checksub:{track_id}",
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

_bot_username: str | None = None


async def ref_link(bot, telegram_id: int) -> str:
    global _bot_username
    if _bot_username is None:
        _bot_username = (await bot.get_me()).username
    return f"https://t.me/{_bot_username}?start=ref_{telegram_id}"


def next_milestone(count: int) -> int:
    return (count // FRIENDS_PER_BONUS + 1) * FRIENDS_PER_BONUS


async def bonuses_available(telegram_id: int) -> int:
    user = await db.get_user(telegram_id)
    if user is None:
        return 0
    earned = await db.count_referrals(telegram_id) // FRIENDS_PER_BONUS
    return max(0, earned - (user["bonus_claimed"] or 0))


def referral_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Скопировать ссылку 🔗", callback_data="copy_ref_link"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Выбрать бонус-трек 🎁", callback_data="catalog"
                )
            ],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
        ]
    )


@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery) -> None:
    count = await db.count_referrals(callback.from_user.id)
    link = await ref_link(callback.bot, callback.from_user.id)
    await callback.message.edit_text(
        REFERRAL_TEXT.format(link=link, count=count, next_milestone=next_milestone(count)),
        reply_markup=referral_kb(),
    )


@router.callback_query(F.data == "copy_ref_link")
async def copy_ref_link(callback: CallbackQuery) -> None:
    link = await ref_link(callback.bot, callback.from_user.id)
    await callback.message.answer(
        f"Ваша пригласительная ссылка — нажмите, чтобы скопировать:\n<code>{link}</code>"
    )


async def _grant_bonus_track(callback: CallbackQuery, track_id: int) -> None:
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    if await db.user_has_track(callback.from_user.id, track_id):
        # повтор после transient-ретрая: трек уже выдан — досылаем файл
        if track["file_id"]:
            await callback.message.answer_audio(
                track["file_id"], title=track["title"]
            )
        return

    await db.increment_bonus_claimed(callback.from_user.id)
    await db.add_user_track(callback.from_user.id, track_id)
    logger.info("User %s claimed bonus track %s", callback.from_user.id, track_id)

    await callback.message.edit_text(
        f"🎁 <b>{track['title']}</b> — ваш бонусный трек!\n\n"
        "Трек придёт следующим сообщением, как только аудиофайл будет загружен в базу. "
        "Советы по прослушиванию — в разделе «📖 Как слушать КИТ».",
    )
    if track["file_id"]:
        await callback.message.answer_audio(track["file_id"], title=track["title"])


@router.callback_query(F.data.startswith("bonus:"))
async def claim_bonus_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    if await bonuses_available(callback.from_user.id) <= 0:
        await callback.answer(
            "Бонусных треков пока нет — пригласите друзей по своей ссылке 🎁",
            show_alert=True,
        )
        return
    sub = await is_subscribed(callback.bot, callback.from_user.id)
    if sub is not True:
        if sub is None:
            await callback.answer(
                "Проверка подписки временно недоступна — попробуйте позже 🙌",
                show_alert=True,
            )
        else:
            await callback.message.edit_text(
                SUBSCRIBE_TEXT.format(channel=settings.channel_username),
                reply_markup=subscribe_kb(track_id),
            )
        return
    await _grant_bonus_track(callback, track_id)


@router.callback_query(F.data.startswith("checksub:"))
async def check_subscription(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    if await bonuses_available(callback.from_user.id) <= 0:
        await callback.answer(
            "Бонусных треков пока нет — пригласите друзей по своей ссылке 🎁",
            show_alert=True,
        )
        return
    sub = await is_subscribed(callback.bot, callback.from_user.id)
    if sub is not True:
        await callback.answer(
            "Подписка не найдена — подпишитесь на канал и нажмите снова 🙌"
            if sub is False
            else "Проверка подписки временно недоступна — попробуйте позже 🙌",
            show_alert=True,
        )
        return
    await _grant_bonus_track(callback, track_id)
