import logging
from datetime import datetime, timezone
from typing import Any

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import db
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# статусы оплаты, при которых трек выдаётся
PAID_STATUSES = {
    "success", "paid", "completed", "complete", "ok", "true", "1",
    "оплачен", "оплачено", "оплачен полностью", "завершен", "завершён",
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

# оффер GetCourse -> med_id видео-медитации (app/meditations.py)
OFFER_ID_TO_MED_ID = {
    8476167: 1,  # Счастье в теле — 900 ₽, page64
    8476247: 2,  # Расслабление в мозге — 500 ₽, page65
    8476264: 3,  # Убрать страхи — 500 ₽, page66
    8476272: 4,  # Позитивные ветки — 1500 ₽, page67
    8476286: 5,  # Техника быстрого исцеления — 300 ₽, page68
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


def _extract_offer(raw: Any) -> tuple[str, int, int] | None:
    """{object.offers} как '8759153' или '8759153,8759154'
    -> ('track'|'med', id продукта в каталоге, id оффера GetCourse)."""
    if raw is None:
        return None
    for part in str(raw).replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            oid = int(part)
            if oid in OFFER_ID_TO_TRACK_ID:
                return ("track", OFFER_ID_TO_TRACK_ID[oid], oid)
            if oid in OFFER_ID_TO_MED_ID:
                return ("med", OFFER_ID_TO_MED_ID[oid], oid)
    return None


async def _deliver_meditation(
    request: Request, telegram_id: int, med: dict, order_number: str
) -> JSONResponse:
    """Выдача купленной видео-медитации: file_id шлём видео, иначе
    подтверждаем покупку текстом и просим админа загрузить файл."""
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return JSONResponse(
            {"status": "error", "error": "bot_not_configured"}, status_code=503
        )

    await db.add_user_meditation(telegram_id, med["med_id"])
    await db.record_order(
        order_number
        or f"auto-{telegram_id}-m{med['med_id']}-{int(datetime.now(timezone.utc).timestamp())}",
        telegram_id,
        None,
        med["offer_id"],
        med["price"],
    )

    if med["file_id"] or med["audio_id"]:
        await bot.send_message(
            telegram_id,
            f"Спасибо за покупку! Ваша медитация «{med['title']}» — "
            "видео и аудиоверсия ниже 🎬🎧",
        )
        caption = f"🎬 <b>{med['title']}</b>"
        audio_caption = f"🎧 <b>{med['title']}</b> — аудиоверсия"
        failed = False
        if med["file_id"]:
            try:
                await bot.send_video(telegram_id, med["file_id"], caption=caption)
            except TelegramAPIError:
                logger.exception(
                    "sendVideo failed for user %s meditation %s — trying sendDocument",
                    telegram_id,
                    med["med_id"],
                )
                try:
                    await bot.send_document(
                        telegram_id, med["file_id"], caption=caption,
                    )
                except TelegramAPIError:
                    logger.exception(
                        "sendDocument also failed for user %s", telegram_id
                    )
                    failed = True
        if med["audio_id"]:
            try:
                await bot.send_audio(
                    telegram_id, med["audio_id"], caption=audio_caption
                )
            except TelegramAPIError:
                logger.exception(
                    "sendAudio failed for user %s meditation %s — trying sendDocument",
                    telegram_id,
                    med["med_id"],
                )
                try:
                    await bot.send_document(
                        telegram_id, med["audio_id"], caption=audio_caption,
                    )
                except TelegramAPIError:
                    logger.exception(
                        "sendDocument also failed for user %s", telegram_id
                    )
                    failed = True
        if failed:
            return JSONResponse(
                {"status": "error", "error": "delivery_failed"},
                status_code=502,
            )
    else:
        await bot.send_message(
            telegram_id,
            f"Спасибо за покупку! Медитация «{med['title']}» скоро придёт — "
            "пришлём видео и аудио вам в этом чате 🙌",
        )
        try:
            await bot.send_message(
                settings.admin_telegram_id,
                f"💳 Покупка медитации «{med['title']}» ({med['price']} ₽) "
                f"от пользователя {telegram_id} — файлы ещё не загружены, "
                "нужны file_id.",
            )
        except TelegramAPIError:
            logger.exception("admin notify failed for meditation purchase")

    try:
        from app.handlers.referral import PURCHASES_BUTTON_TEXT
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        await bot.send_message(
            telegram_id,
            "Все ваши покупки — в разделе «Мои покупки».",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=PURCHASES_BUTTON_TEXT, callback_data="purchases")]
                ]
            ),
        )
    except TelegramAPIError:
        logger.exception("purchases-button message failed for user %s", telegram_id)
    logger.info(
        "Delivered meditation %s to user %s after GetCourse payment",
        med["med_id"],
        telegram_id,
    )
    return JSONResponse({"status": "ok"})


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

    offer = _extract_offer(_pick(payload, OFFER_ID_KEYS))
    track_title = _pick(payload, TRACK_TITLE_KEYS)
    order_number = str(_pick(payload, ("order_number", "order_id", "deal_id")) or "")

    user = await db.get_user(telegram_id)
    if user is None:
        logger.warning("GetCourse payment for unknown telegram_id=%s", telegram_id)
        return JSONResponse(
            {"status": "error", "error": "user_not_found"}, status_code=404
        )

    if offer is not None and offer[0] == "med":
        from app.meditations import get_meditation

        med = get_meditation(offer[1])
        if med is not None:
            return await _deliver_meditation(request, telegram_id, med, order_number)

    track = None
    if offer is not None and offer[0] == "track":
        track = await db.get_track(offer[1])
    if track is None and track_title:
        track = await db.get_track_by_title(str(track_title).strip())
    if track is None:
        logger.warning(
            "GetCourse payment for unknown offer=%r title=%r",
            offer,
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
            await bot.send_document(
                telegram_id, track["file_id"], caption=caption,
            )
        except TelegramAPIError:
            logger.exception("sendDocument also failed for user %s", telegram_id)
            return JSONResponse(
                {"status": "error", "error": "delivery_failed"}, status_code=502
            )

    await db.add_user_track(telegram_id, track["track_id"])
    await db.record_order(
        order_number or f"auto-{telegram_id}-{track['track_id']}-{int(datetime.now(timezone.utc).timestamp())}",
        telegram_id,
        track["track_id"],
        offer[2] if offer else None,
        settings.track_price_rub,
    )
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
