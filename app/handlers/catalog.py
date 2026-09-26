import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from urllib.parse import quote

from app import db
from app.config import settings
from app.keyboards import BACK_LABEL, CB_MENU

logger = logging.getLogger(__name__)

router = Router()

TRACK_PRICE = 900

CATALOG_TITLE = "Выберите, с чем сейчас работаем:"

# разделы каталога из разделов 1.3/2.3 документа
SECTIONS: dict[str, str] = {
    "emotions": "😔 Эмоции и психика",
    "energy": "🌟 Состояние и энергия",
    "body": "💪 Исцеление тела",
}


def catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[
                [InlineKeyboardButton(text=label, callback_data=f"sec:{key}")]
                for key, label in SECTIONS.items()
            ],
            [InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)],
        ]
    )


def section_kb(tracks: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t["title"], callback_data=f"track:{t['track_id']}")]
        for t in tracks
    ]
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад к разделам", callback_data="catalog")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def track_card_text(track, free_available: bool, owned: bool) -> str:
    duration = f"{track['duration_min']} мин" if track["duration_min"] else "—"
    price = "Первый трек — бесплатно" if free_available else f"{TRACK_PRICE} ₽"
    text = (
        f"<b>{track['title']}</b>\n"
        f"Раздел: {SECTIONS.get(track['section'], track['section'])}\n"
        f"Длительность: {duration}\n"
        f"Для чего: {track['description']}\n"
        f"Цена: {price}"
    )
    if owned:
        text += "\n\n🎧 Этот трек уже у вас — найдите его в разделе «💳 Мои покупки»."
    return text


def pay_url(track, telegram_id: int) -> str:
    return settings.getcourse_pay_url_template.format(
        track_id=track["track_id"],
        telegram_id=telegram_id,
        track_title=quote(track["title"]),
    )


def track_kb(
    track,
    free_available: bool,
    owned: bool,
    telegram_id: int,
    bonus_available: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    tid = track["track_id"]
    if not owned:
        if bonus_available:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🎁 Забрать бонус-трек", callback_data=f"bonus:{tid}"
                    )
                ]
            )
        if free_available:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🎁 Забрать бесплатно", callback_data=f"free:{tid}"
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"💳 Купить за {TRACK_PRICE} ₽",
                        url=pay_url(track, telegram_id),
                    )
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🎁 Пригласить 3х друзей и получить бонусом",
                        callback_data="referral",
                    )
                ]
            )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад в раздел", callback_data=f"sec:{track['section']}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery) -> None:
    await callback.message.edit_text(CATALOG_TITLE, reply_markup=catalog_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("sec:"))
async def show_section(callback: CallbackQuery) -> None:
    section = callback.data.split(":", 1)[1]
    tracks = await db.get_tracks_by_section(section)
    if not tracks:
        await callback.answer("В этом разделе пока нет треков", show_alert=True)
        return
    await callback.message.edit_text(
        f"{SECTIONS.get(section, 'Раздел')} — выберите трек:",
        reply_markup=section_kb(tracks),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("track:"))
async def show_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    user = await db.get_user(callback.from_user.id)
    free_available = bool(user) and not user["got_free_track"]
    owned = await db.user_has_track(callback.from_user.id, track_id)
    bonus_available = False
    if user and not free_available:
        earned = await db.count_referrals(callback.from_user.id) // 3
        bonus_available = earned > (user["bonus_claimed"] or 0)
    await callback.message.edit_text(
        track_card_text(track, free_available, owned),
        reply_markup=track_kb(
            track, free_available, owned, callback.from_user.id, bonus_available
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("free:"))
async def claim_free_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    user = await db.get_user(callback.from_user.id)
    if user is None:
        await callback.answer("Нажмите /start для регистрации", show_alert=True)
        return
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    if user["got_free_track"]:
        if await db.user_has_track(callback.from_user.id, track_id):
            # повтор после transient-ретрая: трек уже выдан — досылаем файл
            if track["file_id"]:
                await callback.message.answer_audio(
                    track["file_id"], title=track["title"]
                )
            return
        await callback.answer(
            "Бесплатный трек уже использован — этот можно купить 🙌",
            show_alert=True,
        )
        return

    await db.mark_got_free_track(callback.from_user.id)
    await db.add_user_track(callback.from_user.id, track_id)
    logger.info("User %s claimed free track %s", callback.from_user.id, track_id)

    await callback.message.edit_text(
        f"🎁 <b>{track['title']}</b> — ваш подарок!\n\n"
        "Трек придёт следующим сообщением, как только аудиофайл будет загружен в базу. "
        "Советы по прослушиванию — в разделе «📖 Как слушать КИТ».",
    )
    if track["file_id"]:
        await callback.message.answer_audio(track["file_id"], title=track["title"])
    await callback.answer()

