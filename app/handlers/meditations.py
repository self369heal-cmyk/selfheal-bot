import logging
from urllib.parse import quote

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import db
from app.config import settings
from app.keyboards import BACK_LABEL, CB_MENU
from app.meditations import MEDITATIONS, get_meditation

logger = logging.getLogger(__name__)

router = Router()

MED_TITLE = "🎬 Видео-медитации и практики — выберите:"


def med_list_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{m['button']} · {m['price']} ₽",
                callback_data=f"med:{m['med_id']}",
            )
        ]
        for m in MEDITATIONS
    ]
    rows.append([InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def med_pay_url(med: dict, telegram_id: int) -> str:
    return settings.getcourse_pay_url_template.format(
        track_id=med["med_id"],
        track_slug=med["pay_slug"],
        telegram_id=telegram_id,
        track_title=quote(med["title"]),
    )


def med_card_text(med: dict, owned: bool) -> str:
    text = (
        f"🎬 <b>{med['title']}</b>\n\n"
        f"{med['desc']}\n\n"
        f"Цена: {med['price']} ₽"
    )
    if owned:
        text += "\n\n🎬 Эта медитация уже у вас. Найдите её в разделе «💳 Мои покупки»."
    return text


def med_card_kb(med: dict, owned: bool, telegram_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if owned:
        if med["file_id"] or med["audio_id"]:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="▶️ Смотреть медитацию",
                        callback_data=f"redm:{med['med_id']}",
                        style="success",
                    )
                ]
            )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"💳 Купить за {med['price']} ₽",
                    url=med_pay_url(med, telegram_id),
                    style="success",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ К списку медитаций",
                callback_data="medlist",
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "video")
async def show_meditations(callback: CallbackQuery) -> None:
    await callback.message.edit_text(MED_TITLE, reply_markup=med_list_kb())


@router.callback_query(F.data == "medlist")
async def back_to_meditation_list(callback: CallbackQuery) -> None:
    # карточка — фото-сообщение: удаляем её и показываем список новым сообщением
    try:
        await callback.message.delete()
    except TelegramAPIError:
        pass
    await callback.message.answer(MED_TITLE, reply_markup=med_list_kb())


@router.callback_query(F.data.startswith("med:"))
async def show_meditation(callback: CallbackQuery) -> None:
    med = get_meditation(int(callback.data.split(":", 1)[1]))
    if med is None:
        await callback.answer("Медитация не найдена", show_alert=True)
        return
    owned = await db.user_has_meditation(callback.from_user.id, med["med_id"])
    caption = med_card_text(med, owned)
    kb = med_card_kb(med, owned, callback.from_user.id)
    # список убираем, карточку шлём фото-сообщением
    try:
        await callback.message.delete()
    except TelegramAPIError:
        pass
    try:
        await callback.message.answer_photo(med["image"], caption=caption, reply_markup=kb)
    except TelegramAPIError:
        logger.exception("answer_photo failed for meditation %s — текстовая карточка", med["med_id"])
        await callback.message.answer(caption, reply_markup=kb)


@router.callback_query(F.data.startswith("redm:"))
async def redeliver_meditation(callback: CallbackQuery) -> None:
    med_id = int(callback.data.split(":", 1)[1])
    if not await db.user_has_meditation(callback.from_user.id, med_id):
        await callback.answer("Эта медитация у вас не найдена", show_alert=True)
        return
    med = get_meditation(med_id)
    if med is None or not (med["file_id"] or med["audio_id"]):
        await callback.answer(
            "Файлы ещё загружаются, скоро будут доступны 🙌",
            show_alert=True,
        )
        return
    caption = f"🎬 <b>{med['title']}</b>"
    audio_caption = f"🎧 <b>{med['title']}</b> — аудиоверсия"
    ok = True
    if med["file_id"]:
        try:
            await callback.message.answer_video(med["file_id"], caption=caption)
        except TelegramAPIError:
            logger.exception(
                "Redelivery video failed for user %s meditation %s",
                callback.from_user.id,
                med_id,
            )
            try:
                await callback.message.answer_document(
                    med["file_id"], caption=caption
                )
            except TelegramAPIError:
                ok = False
    if med["audio_id"]:
        try:
            await callback.message.answer_audio(med["audio_id"], caption=audio_caption)
        except TelegramAPIError:
            logger.exception(
                "Redelivery audio failed for user %s meditation %s",
                callback.from_user.id,
                med_id,
            )
            try:
                await callback.message.answer_document(
                    med["audio_id"], caption=audio_caption
                )
            except TelegramAPIError:
                ok = False
    if not ok:
        await callback.answer(
            "Не удалось отправить часть файлов. Напишите в поддержку",
            show_alert=True,
        )
