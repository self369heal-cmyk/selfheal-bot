import logging

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import texts
from app.db import add_referral, count_referrals, create_user, get_user
from app.handlers.referral import BONUS_NOTIFY_TEXT, FRIENDS_PER_BONUS
from app.keyboards import MENU_TITLE, main_menu_kb, open_catalog_kb

logger = logging.getLogger(__name__)

router = Router()

WELCOME_TEXT = """Приветствую 🌿

Я — бот «Тайная природа СамоИсцеления».

Здесь собраны особые исцеляющие аудиотреки, в которые «вшиты» Коды Исцеления Тела.

Каждый трек работает через частоты тела мозга и подсознания (без слов) и помогает телу и психике самим найти путь к балансу и СамоИсцелиться:
- запускает гармоничные процессы в организме
- улучшает самочувствие
- снимает боли и напряжение
- успокаивает психику и убирает стресс.

Первый трек, который вы выберете в каталоге, — ваш в подарок. Остальные можно приобрести дальше, по мере вашего запроса, или получить через реферальную программу приглашения друзей."""


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    telegram_id = message.from_user.id

    referrer_id: int | None = None
    if command.args and command.args.startswith("ref_"):
        try:
            candidate = int(command.args.removeprefix("ref_"))
        except ValueError:
            candidate = None
        if candidate is not None and candidate != telegram_id:
            referrer_id = candidate

    is_new = await get_user(telegram_id) is None
    if is_new:
        await create_user(telegram_id, referrer_id)
        logger.info("New user registered: %s (referrer: %s)", telegram_id, referrer_id)
        if referrer_id is not None:
            await _register_referral(message, referrer_id)

    await message.answer(WELCOME_TEXT, reply_markup=open_catalog_kb())
    if is_new:
        await message.answer(texts.DISCLAIMER)
    await message.answer(MENU_TITLE, reply_markup=main_menu_kb())


async def _register_referral(message: Message, referrer_id: int) -> None:
    await add_referral(referrer_id, message.from_user.id)
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
