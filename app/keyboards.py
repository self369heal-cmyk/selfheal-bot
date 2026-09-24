from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.texts import VLADEMIR_URL

MENU_TITLE = "Главное меню:"

# (callback_data, текст кнопки) — дословно из раздела 2.2 документа
MENU_BUTTONS: list[tuple[str, str]] = [
    ("catalog", "🎧 Каталог треков «Коды Исцеления Тела»"),
    ("howto", "📖 Как слушать КИТ"),
    ("referral", "🎁 Пригласи друга и получи бонус"),
    ("purchases", "💳 Мои покупки"),
    ("support", "💬 Поддержка / вопрос мастеру"),
    ("custom_track", "🎼 Создать индивидуальный трек исцеление или омоложения"),
    ("session", "🗓 Запись на индивидуальный сеанс"),
    ("video", "▶️ Приобрести видео медитации"),
    ("author", "✨ Про автора треков"),
]

CB_MENU = "menu"
CB_CATALOG = "catalog"
BACK_LABEL = "⬅️ В главное меню"


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=data)]
            for data, label in MENU_BUTTONS
        ]
    )


def open_catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть каталог 🎧", callback_data=CB_CATALOG)]
        ]
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)]
        ]
    )


def contact_vlademir_kb(prefill_text: str) -> InlineKeyboardMarkup:
    """Кнопка-ссылка на личку Владемира с предзаполненным текстом + назад."""
    url = f"{VLADEMIR_URL}?text={quote(prefill_text)}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Написать Владемиру ✍️", url=url)],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
        ]
    )
