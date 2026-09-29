from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.texts import VLADEMIR_URL

MENU_TITLE = "Главное меню:"

# (callback_data, текст кнопки, style) — тексты дословно из раздела 2.2 документа
MENU_BUTTONS: list[tuple[str, str, str | None]] = [
    ("catalog", "🔊 Каталог треков «Коды Исцеления Тела»", "primary"),
    ("video", "📹 Каталог видео медитаций", "primary"),
    ("referral", "🎁 Пригласи друга и получи бонус", "success"),
    ("purchases", "💳 Мои покупки", "danger"),
    ("howto", "📖 Как слушать КИТ", None),
    ("support", "💬 Поддержка / вопрос мастеру", None),
    ("custom_track", "🎼 Создать индивидуальный трек исцеление или омоложения", None),
    ("session", "🗓 Запись на индивидуальный сеанс", None),
    ("author", "✨ Про автора треков и технологию", None),
]

CB_MENU = "menu"
CB_CATALOG = "catalog"
BACK_LABEL = "⬅️ В главное меню"


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=data, style=style)]
            for data, label, style in MENU_BUTTONS
        ]
    )


def open_catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть каталог 🔊", callback_data=CB_CATALOG)]
        ]
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)]
        ]
    )


# закреплённая reply-клавиатура 2x2 внизу экрана — ставится один раз в /start
BTN_PURCHASES = "🛍 Мои покупки"
BTN_CATALOG = "🔊 Каталог КИТ"
BTN_REFERRALS = "💌 Мои рефералы"
BTN_REVIEW = "💬 Написать отзыв"

# прежние подписи: закреплённые клавиатуры у пользователей обновляются
# только новым сообщением — старые тексты принимаем тоже
BTN_CATALOG_LEGACY = "📚 Каталог КИТ"
BTN_REFERRALS_LEGACY = "👥 Мои рефералы"

REPLY_KB_ROWS: list[list[str]] = [
    [BTN_PURCHASES, BTN_CATALOG],
    [BTN_REFERRALS, BTN_REVIEW],
]


def persistent_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t) for t in row] for row in REPLY_KB_ROWS
        ],
        resize_keyboard=True,
    )


def contact_vlademir_kb(prefill_text: str | None = None) -> InlineKeyboardMarkup:
    """Кнопка-ссылка на личку Владемира (опц. предзаполненный текст) + назад."""
    url = VLADEMIR_URL
    if prefill_text:
        url = f"{url}?text={quote(prefill_text)}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Написать Владемиру ✍️", url=url)],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
        ]
    )
