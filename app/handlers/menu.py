import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import texts
from app.keyboards import (
    CB_MENU,
    MENU_TITLE,
    back_to_menu_kb,
    contact_vlademir_kb,
    main_menu_kb,
)

logger = logging.getLogger(__name__)

router = Router()

# кнопки меню, разделы которых появятся на следующих шагах сценария
STUB_SECTIONS = {"purchases", "support", "video"}

SECTION_SCREENS: dict[str, tuple[str, object]] = {
    "howto": (texts.HOW_TO_LISTEN, None),
    "author": (texts.ABOUT_AUTHOR, None),
    "custom_track": (texts.CUSTOM_TRACK, texts.CUSTOM_TRACK_PREFILL),
    "session": (texts.SESSION, texts.SESSION_PREFILL),
}


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(MENU_TITLE, reply_markup=main_menu_kb())


@router.callback_query(F.data == CB_MENU)
async def show_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(MENU_TITLE, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data.in_(SECTION_SCREENS.keys()))
async def show_section(callback: CallbackQuery) -> None:
    text, prefill = SECTION_SCREENS[callback.data]
    kb = (
        contact_vlademir_kb(prefill) if prefill else back_to_menu_kb()
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.in_(STUB_SECTIONS))
async def stub_section(callback: CallbackQuery) -> None:
    await callback.answer(
        "Этот раздел появится на следующих шагах 🚧", show_alert=True
    )
