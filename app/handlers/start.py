import logging

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app.db import create_user, get_user
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

    if await get_user(telegram_id) is None:
        await create_user(telegram_id, referrer_id)
        logger.info("New user registered: %s (referrer: %s)", telegram_id, referrer_id)

    await message.answer(WELCOME_TEXT, reply_markup=open_catalog_kb())
    await message.answer(MENU_TITLE, reply_markup=main_menu_kb())
