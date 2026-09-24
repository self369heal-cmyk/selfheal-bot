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

# кнопки меню, разделы которых появятся на следующих шагах сценария
STUB_SECTIONS = {"referral", "purchases", "support", "video"}

CATALOG_TITLE = "Выберите, с чем сейчас работаем:"

# разделы каталога из раздела 1.3/2.3 документа (списки треков — следующий шаг)
CATALOG_SECTIONS: list[tuple[str, str]] = [
    ("sec_emotions", "😔 Эмоции и психика"),
    ("sec_energy", "🌟 Состояние и энергия"),
    ("sec_body", "💪 Исцеление тела"),
]


def _catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[
                [InlineKeyboardButton(text=label, callback_data=data)]
                for data, label in CATALOG_SECTIONS
            ],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
        ]
    )

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


@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery) -> None:
    await callback.message.edit_text(CATALOG_TITLE, reply_markup=_catalog_kb())
    await callback.answer()


@router.callback_query(F.data.in_(STUB_SECTIONS))
async def stub_section(callback: CallbackQuery) -> None:
    await callback.answer(
        "Этот раздел появится на следующих шагах 🚧", show_alert=True
    )
