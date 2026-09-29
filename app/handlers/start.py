import logging
import re

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db import add_referral, count_referrals, create_user, get_user
from app.handlers.referral import BONUS_NOTIFY_TEXT, FRIENDS_PER_BONUS
from app.keyboards import (
    MENU_TITLE,
    main_menu_kb,
    open_catalog_kb,
    persistent_kb,
)
from app.retry import retry_transient

logger = logging.getLogger(__name__)

router = Router()

WELCOME_TEXT = """Приветствую 🌿

Я бот «Тайная природа СамоИсцеления». Здесь собраны исцеляющие аудиотреки со «вшитыми» <b>Кодами Исцеления Тела</b>.

Каждый трек работает через частоты тела, мозга и подсознания без слов и помогает телу и психике самим найти путь к балансу и СамоИсцелиться:
• запускает гармоничные процессы в организме
• улучшает самочувствие
• снимает боли и напряжение
• успокаивает психику и убирает стресс

Первый трек из каталога вы получаете <b>в подарок</b> 🎁

Остальные можно приобрести по мере вашего запроса или получить бонусом за приглашение друзей."""


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    telegram_id = message.from_user.id

    # реф-параметр: ref<uid> или ref<uid>_track<tid> (трек, приведший человека)
    referrer_id: int | None = None
    source_track_id: int | None = None
    m = re.fullmatch(r"ref_?(\d+)(?:_track(\d+))?", (command.args or "").strip())
    if m:
        candidate = int(m.group(1))
        if candidate != telegram_id:
            referrer_id = candidate
            if m.group(2):
                source_track_id = int(m.group(2))

    is_new = await retry_transient(lambda: get_user(telegram_id)) is None
    if is_new:
        await retry_transient(lambda: create_user(telegram_id, referrer_id))
        logger.info("New user registered: %s (referrer: %s)", telegram_id, referrer_id)
        if referrer_id is not None:
            await retry_transient(
                lambda: _register_referral(message, referrer_id, source_track_id)
            )

    await message.answer(WELCOME_TEXT, reply_markup=open_catalog_kb())
    await message.answer(MENU_TITLE, reply_markup=main_menu_kb())
    # закреплённая reply-клавиатура 2x2 внизу экрана — ставится один раз здесь
    await message.answer("📍 Быстрые разделы:", reply_markup=persistent_kb())


async def _register_referral(
    message: Message, referrer_id: int, source_track_id: int | None = None
) -> None:
    await add_referral(referrer_id, message.from_user.id, source_track_id)
    count = await count_referrals(referrer_id)
    if count % FRIENDS_PER_BONUS != 0:
        return
    try:
        await message.bot.send_message(
            referrer_id,
            BONUS_NOTIFY_TEXT.format(count=count),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Выбрать бонус-трек 🎁", callback_data="catalog"
                        )
                    ]
                ]
            ),
        )
    except TelegramAPIError:
        logger.warning(
            "Cannot notify referrer %s about %s referrals", referrer_id, count
        )
