import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import texts
from app.retry import TRANSIENT_ERRORS, retry_transient
from app.keyboards import (
    CB_MENU,
    MENU_TITLE,
    back_to_menu_kb,
    contact_vlademir_kb,
    main_menu_kb,
)

logger = logging.getLogger(__name__)

router = Router()

SECTION_SCREENS: dict[str, tuple[str, object]] = {
    "howto": (texts.HOW_TO_LISTEN, None),
    "custom_track": (texts.CUSTOM_TRACK, texts.CUSTOM_TRACK_PREFILL),
    "session": (texts.SESSION, texts.SESSION_PREFILL),
    "support": (texts.SUPPORT, ""),
}


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(MENU_TITLE, reply_markup=main_menu_kb())


@router.callback_query(F.data == CB_MENU)
async def show_menu(callback: CallbackQuery) -> None:
    if callback.message.photo:
        # фото-экран (каталог) нельзя превратить в текст — шлём меню новым сообщением;
        # сначала отправка, потом удаление — при сбое экран не потеряется
        await callback.message.answer(MENU_TITLE, reply_markup=main_menu_kb())
        try:
            await callback.message.delete()
        except TelegramAPIError:
            logger.warning("show_menu: failed to delete photo screen")
            try:
                await callback.message.edit_reply_markup()
            except TelegramAPIError:
                pass
    else:
        await callback.message.edit_text(MENU_TITLE, reply_markup=main_menu_kb())


@router.callback_query(F.data.in_(SECTION_SCREENS.keys()))
async def show_section(callback: CallbackQuery) -> None:
    text, prefill = SECTION_SCREENS[callback.data]
    if prefill is None:
        kb = back_to_menu_kb()
    else:
        kb = contact_vlademir_kb(prefill or None)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "author")
async def show_author(callback: CallbackQuery) -> None:
    # дисклеймер и автор идут отдельными сообщениями и остаются в чате;
    # retry на каждое сообщение, чтобы повтор хендлера не дублировал их
    for text in (texts.DISCLAIMER, texts.ABOUT_AUTHOR):
        try:
            await retry_transient(lambda t=text: callback.message.answer(t))
        except TRANSIENT_ERRORS:
            logger.exception("failed to send author screen message")
    # меню выводим заново внизу: старое сообщение меню остаётся выше этих двух
    try:
        await retry_transient(
            lambda: callback.message.answer(MENU_TITLE, reply_markup=main_menu_kb())
        )
    except TRANSIENT_ERRORS:
        logger.exception("failed to resend menu after author screen")


# «video» обрабатывает app.handlers.meditations — там каталог из 5 медитаций
