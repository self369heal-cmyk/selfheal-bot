import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import db
from app.config import settings
from app.keyboards import BACK_LABEL, CB_MENU
from app.subscription import is_subscribed, require_subscription

logger = logging.getLogger(__name__)

router = Router()

FRIENDS_PER_BONUS = 3

REFERRAL_TEXT = """Приглашайте друзей и получайте треки в подарок 🎁

Пригласите <b>3 друзей</b>, которые запустят бота по вашей ссылке, и вы получите ещё один трек бонусом на выбор из каталога.

За каждые следующие 3 приглашённых друга начисляется новый бонус-трек на выбор.

🔗 Ваша ссылка: {link}
Приглашено друзей: {count} из {next_milestone}"""

BONUS_NOTIFY_TEXT = (
    "🎉 Отлично! Вы пригласили уже {count} друзей. "
    "У вас открыт бонус: <b>ещё один трек</b> на выбор из каталога 🎁"
)

_bot_username: str | None = None


async def ref_link(bot, telegram_id: int, track_id: int | None = None) -> str:
    """Персональная реф-ссылка: ref<uid> или ref<uid>_track<tid> для треков."""
    global _bot_username
    if _bot_username is None:
        _bot_username = (await bot.get_me()).username
    param = f"ref{telegram_id}"
    if track_id is not None:
        param += f"_track{track_id}"
    return f"https://t.me/{_bot_username}?start={param}"


MAX_CAPTION_LEN = 1024


async def track_caption(bot, telegram_id: int, track, prefix: str = "") -> str:
    """Caption к аудио: описание трека + строка с персональной ссылкой.

    Лимит Telegram — 1024 символа: при переполнении режем описание,
    ссылку не трогаем.
    """
    link = await ref_link(bot, telegram_id, track["track_id"])
    suffix = (
        "\n\n\nВаша реферальная ссылка для приглашения друзей:"
        f"\n🔗 {link}"
    )
    description = track["description"] or ""
    if len(prefix) + len(description) + len(suffix) > MAX_CAPTION_LEN:
        budget = MAX_CAPTION_LEN - len(prefix) - len(suffix) - 1
        description = description[:budget].rstrip() + "…"
    return f"{prefix}{description}{suffix}"


PURCHASES_BUTTON_TEXT = "💳 Мои покупки"


def purchases_kb() -> InlineKeyboardMarkup:
    """Одна кнопка «Мои покупки» — отдельное сообщение после выдачи трека."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=PURCHASES_BUTTON_TEXT, callback_data="purchases")]
        ]
    )


async def send_track(message, telegram_id: int, track) -> None:
    """Аудио с caption + отдельное сообщение с кнопкой «Мои покупки»."""
    await message.answer_audio(
        track["file_id"],
        title=track["title"],
        caption=await track_caption(message.bot, telegram_id, track),
    )
    await message.answer(
        "Все ваши треки — в разделе «Мои покупки».",
        reply_markup=purchases_kb(),
    )


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
        f"Ваша пригласительная ссылка (нажмите, чтобы скопировать):\n<code>{link}</code>"
    )


async def _grant_bonus_track(callback: CallbackQuery, track_id: int) -> None:
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    if await db.user_has_track(callback.from_user.id, track_id):
        # повтор после transient-ретрая: трек уже выдан — досылаем файл
        if track["file_id"]:
            await send_track(callback.message, callback.from_user.id, track)
        return

    await db.increment_bonus_claimed(callback.from_user.id)
    await db.add_user_track(callback.from_user.id, track_id)
    logger.info("User %s claimed bonus track %s", callback.from_user.id, track_id)

    await callback.message.edit_text(
        f"🎁 <b>{track['title']}</b>: ваш бонусный трек!\n\n"
        "Трек придёт следующим сообщением. Желательно перед запуском трека "
        "<b>выбрать намерение и свой желаемый результат</b>. "
        "Слушайте на любой комфортной громкости и любое количество времени до результата. "
        "Наушники не обязательно, можно слушать из телефона на минимальной громкости.\n\n"
        "Подробные рекомендации по прослушиванию в разделе «📖 Как слушать КИТ».",
    )
    if track["file_id"]:
        await send_track(callback.message, callback.from_user.id, track)


@router.callback_query(F.data.startswith("bonus:"))
async def claim_bonus_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    if await bonuses_available(callback.from_user.id) <= 0:
        await callback.answer(
            "Бонусных треков пока нет. Пригласите друзей по своей ссылке 🎁",
            show_alert=True,
        )
        return
    if not await require_subscription(callback, track_id, "bonus"):
        return
    await _grant_bonus_track(callback, track_id)


@router.callback_query(F.data.startswith("checksub:"))
async def check_subscription(callback: CallbackQuery) -> None:
    _, kind, tid = callback.data.split(":", 2)
    track_id = int(tid)
    sub = await is_subscribed(callback.bot, callback.from_user.id)
    if sub is not True:
        await callback.answer(
            "Подписка не найдена. Подпишитесь на канал и нажмите снова 🙌"
            if sub is False
            else "Проверка подписки временно недоступна. Попробуйте позже 🙌",
            show_alert=True,
        )
        return
    if kind == "free":
        from app.handlers.catalog import _deliver_free_track

        user = await db.get_user(callback.from_user.id)
        if user is None:
            await callback.answer("Нажмите /start для регистрации", show_alert=True)
            return
        track = await db.get_track(track_id)
        if track is None:
            await callback.answer("Трек не найден", show_alert=True)
            return
        await _deliver_free_track(callback, user, track)
        return
    if await bonuses_available(callback.from_user.id) <= 0:
        await callback.answer(
            "Бонусных треков пока нет. Пригласите друзей по своей ссылке 🎁",
            show_alert=True,
        )
        return
    await _grant_bonus_track(callback, track_id)
