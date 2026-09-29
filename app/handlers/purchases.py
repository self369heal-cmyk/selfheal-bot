import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import db
from app.handlers.referral import PURCHASES_BUTTON_TEXT, track_caption
from app.keyboards import BACK_LABEL, CB_MENU
from app.meditations import get_meditation

logger = logging.getLogger(__name__)

router = Router()

PURCHASES_TITLE = "Вот все треки и медитации, которые у вас уже есть 🔊🎬"
PURCHASES_EMPTY = (
    "У вас пока нет треков.\n\nЗагляните в каталог: <b>первый трек в подарок 🎁</b>"
)


def purchases_kb(tracks: list, med_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📥 {t['title']} · скачать ещё раз",
                callback_data=f"redl:{t['track_id']}",
            )
        ]
        for t in tracks
    ]
    for med_id in med_ids:
        med = get_meditation(med_id)
        if med is None:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"▶️ {med['button']} · смотреть",
                    callback_data=f"redm:{med_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def purchases_view(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Текст + клавиатура раздела «Мои покупки» — общий рендер для
    inline-коллбека и reply-кнопки."""
    tracks = await db.get_user_tracks(telegram_id)
    med_ids = [row["med_id"] for row in await db.get_user_meditations(telegram_id)]
    if not tracks and not med_ids:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔊 В каталог", callback_data="catalog"
                    )
                ],
                [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
            ]
        )
        return PURCHASES_EMPTY, kb
    return PURCHASES_TITLE, purchases_kb(tracks, med_ids)


@router.callback_query(F.data == "purchases")
async def show_purchases(callback: CallbackQuery) -> None:
    text, kb = await purchases_view(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("redl:"))
async def redeliver_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    if not await db.user_has_track(callback.from_user.id, track_id):
        await callback.answer("Этот трек у вас не найден", show_alert=True)
        return
    track = await db.get_track(track_id)
    if track is None or not track["file_id"]:
        await callback.answer(
            "Файл этого трека ещё не загружен, скоро будет доступен 🙌",
            show_alert=True,
        )
        return
    caption = await track_caption(callback.bot, callback.from_user.id, track)
    try:
        await callback.message.answer_audio(
            track["file_id"], title=track["title"], caption=caption,
        )
    except TelegramAPIError:
        logger.exception(
            "Redelivery failed for user %s track %s",
            callback.from_user.id,
            track_id,
        )
        try:
            await callback.message.answer_document(
                track["file_id"], caption=caption,
            )
        except TelegramAPIError:
            await callback.answer(
                "Не удалось отправить файл. Напишите в поддержку",
                show_alert=True,
            )
            return
    await callback.message.answer(
        "Все ваши треки — в разделе «Мои покупки».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=PURCHASES_BUTTON_TEXT, callback_data="purchases")]
            ]
        ),
    )
