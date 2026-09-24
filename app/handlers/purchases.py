import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import db
from app.keyboards import BACK_LABEL, CB_MENU

logger = logging.getLogger(__name__)

router = Router()

PURCHASES_TITLE = "Вот все треки, которые у вас уже есть 🎧"
PURCHASES_EMPTY = (
    "У вас пока нет треков — загляните в каталог: первый трек — в подарок 🎁"
)


def purchases_kb(tracks: list) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{t['title']} — получить файл ещё раз 📥",
                callback_data=f"redl:{t['track_id']}",
            )
        ]
        for t in tracks
    ]
    rows.append([InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "purchases")
async def show_purchases(callback: CallbackQuery) -> None:
    tracks = await db.get_user_tracks(callback.from_user.id)
    if not tracks:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎧 В каталог", callback_data="catalog"
                    )
                ],
                [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
            ]
        )
        await callback.message.edit_text(PURCHASES_EMPTY, reply_markup=kb)
        await callback.answer()
        return
    await callback.message.edit_text(
        PURCHASES_TITLE, reply_markup=purchases_kb(tracks)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("redl:"))
async def redeliver_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    if not await db.user_has_track(callback.from_user.id, track_id):
        await callback.answer("Этот трек у вас не найден", show_alert=True)
        return
    track = await db.get_track(track_id)
    if track is None or not track["file_id"]:
        await callback.answer(
            "Файл этого трека ещё не загружен — скоро будет доступен 🙌",
            show_alert=True,
        )
        return
    try:
        await callback.message.answer_audio(
            track["file_id"], title=track["title"]
        )
    except TelegramAPIError:
        logger.exception(
            "Redelivery failed for user %s track %s",
            callback.from_user.id,
            track_id,
        )
        try:
            await callback.message.answer_document(track["file_id"])
        except TelegramAPIError:
            await callback.answer(
                "Не удалось отправить файл — напишите в поддержку",
                show_alert=True,
            )
            return
    await callback.answer()
