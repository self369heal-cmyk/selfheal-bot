import logging
from typing import Any

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import db

logger = logging.getLogger(__name__)

router = APIRouter()

# статусы оплаты, при которых трек выдаётся
PAID_STATUSES = {"success", "paid", "completed", "complete", "ok", "true", "1"}

# допустимые ключи полей в payload GetCourse
TG_ID_KEYS = ("telegram_id", "tg_id", "user_id", "chat_id")
TRACK_TITLE_KEYS = ("track", "track_title", "title", "product_name", "offer_name")
STATUS_KEYS = ("status", "payment_status", "deal_status")


def _pick(payload: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


@router.post("")
async def getcourse_webhook(request: Request) -> JSONResponse:
    """Вебхук оплаты GetCourse.

    Ожидает telegram_id, название купленного трека и статус оплаты
    (JSON или form-data). При успешной оплате записывает покупку в
    user_tracks и отправляет трек пользователю по file_id.
    """
    if "application/json" in request.headers.get("content-type", ""):
        payload: dict = await request.json()
    else:
        payload = dict(await request.form())
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

    track_title = _pick(payload, TRACK_TITLE_KEYS)
    if not track_title:
        return JSONResponse(
            {"status": "error", "error": "missing_track_title"}, status_code=400
        )

    user = await db.get_user(telegram_id)
    if user is None:
        logger.warning("GetCourse payment for unknown telegram_id=%s", telegram_id)
        return JSONResponse(
            {"status": "error", "error": "user_not_found"}, status_code=404
        )

    track = await db.get_track_by_title(str(track_title).strip())
    if track is None:
        logger.warning("GetCourse payment for unknown track title=%r", track_title)
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

    try:
        await bot.send_audio(
            telegram_id,
            track["file_id"],
            title=track["title"],
            caption="Спасибо за покупку 🎧 Советы по прослушиванию — в разделе «📖 Как слушать КИТ».",
        )
    except TelegramAPIError:
        logger.exception(
            "sendAudio failed for user %s track %s — trying sendDocument",
            telegram_id,
            track["track_id"],
        )
        try:
            await bot.send_document(telegram_id, track["file_id"])
        except TelegramAPIError:
            logger.exception("sendDocument also failed for user %s", telegram_id)
            return JSONResponse(
                {"status": "error", "error": "delivery_failed"}, status_code=502
            )

    await db.add_user_track(telegram_id, track["track_id"])
    logger.info(
        "Delivered track %s to user %s after GetCourse payment",
        track["track_id"],
        telegram_id,
    )
    return JSONResponse({"status": "ok"})
