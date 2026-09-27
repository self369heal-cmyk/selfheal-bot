import logging
from typing import Any

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import db

logger = logging.getLogger(__name__)

router = APIRouter()

# статусы оплаты, при которых трек выдаётся
PAID_STATUSES = {
    "success", "paid", "completed", "complete", "ok", "true", "1",
    "оплачен", "оплачено", "оплачен полностью",
}

# допустимые ключи полей в payload GetCourse
TG_ID_KEYS = ("telegram_id", "tg_id", "user_id", "chat_id")
TRACK_TITLE_KEYS = ("track", "track_title", "title", "product_name", "offer_name")
OFFER_ID_KEYS = ("offer_id", "offers")
STATUS_KEYS = ("status", "payment_status", "deal_status")

# оффер GetCourse -> track_id каталога (названия в GC и в боте расходятся,
# поэтому матчинг по id оффера надёжнее, чем по названию)
OFFER_ID_TO_TRACK_ID = {
    8759153: 1,   # АнтиСтресс и расслабление
    8759155: 2,   # Устранение негативных эмоций
    8759160: 3,   # Хороший сон
    8759319: 4,   # Хорошее настроение
    8759168: 5,   # Концентрация
    8759173: 6,   # Энергичность
    8759174: 7,   # Деньги и изобилие
    8759177: 8,   # Связь с Душой и Богом
    8759181: 9,   # Здоровая спина
    8759182: 10,  # Здоровая голова
    8759183: 11,  # Пищеварение
    8759186: 12,  # Иммунитет
}


def _pick(payload: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


async def _collect_payload(request: Request) -> dict:
    # GC «Вызвать url» может слать GET (параметры в query) или POST
    # (query + тело form/json) — собираем всё в один dict
    payload: dict = dict(request.query_params)
    if request.method == "POST":
        if "application/json" in request.headers.get("content-type", ""):
            payload.update(await request.json())
        else:
            payload.update(dict(await request.form()))
    return payload


def _extract_offer_id(raw: Any) -> int | None:
    """{object.offers} может прийти как '8759153' или '8759153,8759154'."""
    if raw is None:
        return None
    for part in str(raw).replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit() and int(part) in OFFER_ID_TO_TRACK_ID:
            return int(part)
    return None


@router.get("")
@router.post("")
async def getcourse_webhook(request: Request) -> JSONResponse:
    """Вебхук оплаты GetCourse.

    Ожидает telegram_id (или tg_id из utm_term), offer_id/название купленного
    трека и статус оплаты. При успешной оплате записывает покупку в
    user_tracks и отправляет трек пользователю по file_id.
    """
    payload = await _collect_payload(request)
    logger.info("GetCourse webhook received: %s", payload)

    status = str(_pick(payload, STATUS_KEYS) or "").strip().lower()
    if status and status not in PAID_STATUSES:
        return JSONResponse({"status": "ignored", "reason": f"status={status}"})

    raw_tg_id = _pick(payload, TG_ID_KEYS)
    try:
        telegram_id = int(raw_tg_id)
    except (TypeError, ValueError):
        return JSONResponse(
            {"status": "error", "error": "missing_or_bad_telegram_id"},
            status_code=400,
        )

    offer_id = _extract_offer_id(_pick(payload, OFFER_ID_KEYS))
    track_title = _pick(payload, TRACK_TITLE_KEYS)

    user = await db.get_user(telegram_id)
    if user is None:
        logger.warning("GetCourse payment for unknown telegram_id=%s", telegram_id)
        return JSONResponse(
            {"status": "error", "error": "user_not_found"}, status_code=404
        )

    track = None
    if offer_id is not None:
        track = await db.get_track(OFFER_ID_TO_TRACK_ID[offer_id])
    if track is None and track_title:
        track = await db.get_track_by_title(str(track_title).strip())
    if track is None:
        logger.warning(
            "GetCourse payment for unknown offer_id=%r title=%r",
            offer_id,
            track_title,
        )
        return JSONResponse(
            {"status": "error", "error": "track_not_found"}, status_code=404
        )

    if not track["file_id"]:
        logger.error("Track %s has no file_id — cannot deliver", track["track_id"])
        return JSONResponse(
            {"status": "error", "error": "track_has_no_file_id"}, status_code=409
        )

    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return JSONResponse(
            {"status": "error", "error": "bot_not_configured"}, status_code=503
        )

    from app.handlers.referral import track_caption

    caption = await track_caption(
        bot, telegram_id, track, prefix="Спасибо за покупку 🔊\n\n"
    )
    try:
        await bot.send_audio(
            telegram_id,
            track["file_id"],
            title=track["title"],
            caption=caption,
        )
    except TelegramAPIError:
        logger.exception(
            "sendAudio failed for user %s track %s — trying sendDocument",
            telegram_id,
            track["track_id"],
        )
        try:
            await bot.send_document(telegram_id, track["file_id"], caption=caption)
        except TelegramAPIError:
            logger.exception("sendDocument also failed for user %s", telegram_id)
            return JSONResponse(
                {"status": "error", "error": "delivery_failed"}, status_code=502
            )

    await db.add_user_track(telegram_id, track["track_id"])
    try:
        from app.handlers.referral import PURCHASES_BUTTON_TEXT
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        await bot.send_message(
            telegram_id,
            "Все ваши треки — в разделе «Мои покупки».",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=PURCHASES_BUTTON_TEXT, callback_data="purchases")]
                ]
            ),
        )
    except TelegramAPIError:
        logger.exception("purchases-button message failed for user %s", telegram_id)
    logger.info(
        "Delivered track %s to user %s after GetCourse payment",
        track["track_id"],
        telegram_id,
    )
    return JSONResponse({"status": "ok"})
