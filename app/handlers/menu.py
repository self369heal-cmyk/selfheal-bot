import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app import texts
from app.keyboards import (
    BACK_LABEL,
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
    "author": (texts.ABOUT_AUTHOR, None),
    "custom_track": (texts.CUSTOM_TRACK, texts.CUSTOM_TRACK_PREFILL),
    "session": (texts.SESSION, texts.SESSION_PREFILL),
    "support": (texts.SUPPORT, ""),
}


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(MENU_TITLE, reply_markup=main_menu_kb())


@router.callback_query(F.data == CB_MENU)
async def show_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(MENU_TITLE, reply_markup=main_menu_kb())


@router.callback_query(F.data.in_(SECTION_SCREENS.keys()))
async def show_section(callback: CallbackQuery) -> None:
    text, prefill = SECTION_SCREENS[callback.data]
    if prefill is None:
        kb = back_to_menu_kb()
    else:
        kb = contact_vlademir_kb(prefill or None)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "video")
async def show_video(callback: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Перейти на сайт ▶️", url=texts.VIDEO_URL
                )
            ],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
        ]
    )
    await callback.message.edit_text(texts.VIDEO, reply_markup=kb)
