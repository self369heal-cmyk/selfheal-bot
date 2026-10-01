import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import db
from app.handlers.catalog import (
    CATALOG_PHOTO_FILE_ID,
    SECTION_ORDER,
    SECTION_SHORT,
    SECTIONS,
    TRACK_PHOTO_FILE_IDS,
    TRACK_PRICE,
    TRACK_SHORT,
    _catalog_to_message,
    _photo_card,
    pay_url,
    track_card_text,
)
from app.handlers.referral import track_caption
from app.keyboards import BACK_LABEL, CB_MENU
from app.meditations import get_meditation

logger = logging.getLogger(__name__)

router = Router()

PURCHASES_TITLE = (
    "💳 <b>Мои покупки</b>\n\n"
    "🟢 зелёные треки — уже у вас, нажмите, чтобы скачать ещё раз.\n"
    "🔴 красные — ещё не куплены.\n"
)


async def purchases_view(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран «Мои покупки» — как каталог КИТ: постер + все 12 треков,
    купленные зелёные, остальные красные. Общий рендер для
    inline-коллбека и reply-кнопки."""
    tracks = await db.get_all_tracks()
    owned = {r["track_id"] for r in await db.get_user_tracks(telegram_id)}
    med_ids = [row["med_id"] for row in await db.get_user_meditations(telegram_id)]

    lines: list[str] = [PURCHASES_TITLE, ""]
    for sec in SECTION_ORDER:
        lines.append(f"<b>{SECTIONS[sec]}</b>")
        for t in tracks:
            if t["section"] == sec:
                mark = "✅ " if t["track_id"] in owned else ""
                main, _, rest = t["title"].partition(" (")
                rest = f" ({rest}" if rest else ""
                lines.append(f"{mark}{t['track_id']}. <b>{main}</b>{rest}")
        lines.append("")
    if not owned and not med_ids:
        lines.append("Пока купленных нет — 🎁 первый трек в подарок в «🔊 Каталог КИТ».")
    text = "\n".join(lines).rstrip()

    rows: list[list[InlineKeyboardButton]] = []
    for sec in SECTION_ORDER:
        rows.append(
            [InlineKeyboardButton(text=SECTION_SHORT[sec], callback_data="noop", style="primary")]
        )
        pair: list[InlineKeyboardButton] = []
        for t in tracks:
            if t["section"] != sec:
                continue
            is_owned = t["track_id"] in owned
            mark = "✅ " if is_owned else ""
            pair.append(
                InlineKeyboardButton(
                    text=f"{mark}{t['track_id']}. {TRACK_SHORT.get(t['track_id'], t['title'])}",
                    callback_data=f"ptrack:{t['track_id']}",
                    style="success" if is_owned else "danger",
                )
            )
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
    for med_id in med_ids:
        med = get_meditation(med_id)
        if med is None:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"▶️ {med['button']} · смотреть",
                    callback_data=f"redm:{med_id}",
                    style="success",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _back_to_purchases_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к покупкам",
                    callback_data="purchases",
                    style="danger",
                )
            ]
        ]
    )


def _ptrack_kb(
    track,
    free_available: bool,
    telegram_id: int,
    bonus_available: bool,
) -> InlineKeyboardMarkup:
    """Кнопки карточки НЕкупленного трека из «Мои покупок» — те же варианты
    получения, что в каталоге; назад — к покупкам. Купленные выдаются сразу."""
    rows: list[list[InlineKeyboardButton]] = []
    tid = track["track_id"]
    if bonus_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎁 Забрать бонус-трек",
                    callback_data=f"bonus:{tid}",
                    style="success",
                )
            ]
        )
    if free_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎁 Забрать бесплатно",
                    callback_data=f"free:{tid}",
                    style="success",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"💳 Купить за {TRACK_PRICE} ₽",
                    url=pay_url(track, telegram_id),
                    style="success",
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
                text="⬅️ Назад к покупкам",
                callback_data="purchases",
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "purchases")
async def show_purchases(callback: CallbackQuery) -> None:
    text, kb = await purchases_view(callback.from_user.id)
    await _catalog_to_message(callback.message, text, kb)


@router.callback_query(F.data.startswith("ptrack:"))
async def show_purchased_track(callback: CallbackQuery) -> None:
    """Карточка трека из «Мои покупок» — та же картинка и описание, что в каталоге."""
    track_id = int(callback.data.split(":", 1)[1])
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    user = await db.get_user(callback.from_user.id)
    free_available = bool(user) and not user["got_free_track"]
    owned = await db.user_has_track(callback.from_user.id, track_id)
    if owned:
        # купленный трек — сразу выдача: обложка + аудио с описанием и реф-ссылкой
        if not track["file_id"]:
            await callback.answer(
                "Файл этого трека ещё не загружен, скоро будет доступен 🙌",
                show_alert=True,
            )
            return
        caption = await track_caption(callback.bot, callback.from_user.id, track)
        photo_id = TRACK_PHOTO_FILE_IDS.get(track_id, CATALOG_PHOTO_FILE_ID)
        # единым сообщением нельзя: Telegram не принимает thumbnail по file_id,
        # а аплоад байтов через Worker-релей недоступен — шлём фото + аудио.
        # Кнопка «назад» — на самом аудио, без отдельного меню внизу
        try:
            await callback.message.answer_photo(photo=photo_id)
            await callback.message.answer_audio(
                track["file_id"],
                title=track["title"],
                caption=caption,
                reply_markup=_back_to_purchases_kb(),
            )
        except TelegramAPIError:
            logger.exception(
                "Delivery failed for user %s track %s",
                callback.from_user.id,
                track_id,
            )
            await callback.answer(
                "Не удалось отправить файл. Напишите в поддержку",
                show_alert=True,
            )
            return
    bonus_available = False
    if user and not free_available and not owned:
        earned = await db.count_referrals(callback.from_user.id) // 3
        bonus_available = earned + (user["promo_bonus"] or 0) > (user["bonus_claimed"] or 0)
    await _photo_card(
        callback,
        TRACK_PHOTO_FILE_IDS.get(track_id, CATALOG_PHOTO_FILE_ID),
        track_card_text(track, free_available, owned),
        _ptrack_kb(
            track, free_available, callback.from_user.id, bonus_available
        ),
    )


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
            track["file_id"],
            title=track["title"],
            caption=caption,
            reply_markup=_back_to_purchases_kb(),
        )
    except TelegramAPIError:
        logger.exception(
            "Redelivery failed for user %s track %s",
            callback.from_user.id,
            track_id,
        )
        try:
            await callback.message.answer_document(
                track["file_id"],
                caption=caption,
                reply_markup=_back_to_purchases_kb(),
            )
        except TelegramAPIError:
            await callback.answer(
                "Не удалось отправить файл. Напишите в поддержку",
                show_alert=True,
            )
            return
