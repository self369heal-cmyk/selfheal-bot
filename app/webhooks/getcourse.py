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
FIRST_NAME_KEYS = ("first_name", "name", "user_first_name")
LAST_NAME_KEYS = ("last_name", "surname", "user_last_name")
EMAIL_KEYS = ("email", "user_email")
PHONE_KEYS = ("phone", "user_phone", "telephone")
AMOUNT_KEYS = ("cost", "amount", "sum", "cost_money_value", "money_value")

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


def _extract_customer(payload: dict) -> dict:
    """Общий разбор полей покупателя из payload GetCourse."""
    first = str(_pick(payload, FIRST_NAME_KEYS) or "").strip()
    last = str(_pick(payload, LAST_NAME_KEYS) or "").strip()
    raw_amount = _pick(payload, AMOUNT_KEYS)
    try:
        amount = int(float(str(raw_amount).replace(",", "."))) if raw_amount else 0
    except (TypeError, ValueError):
        amount = 0
    return {
        "name": " ".join(p for p in (first, last) if p) or None,
        "email": str(_pick(payload, EMAIL_KEYS) or "").strip() or None,
        "phone": str(_pick(payload, PHONE_KEYS) or "").strip() or None,
        "amount": amount,
    }


async def _notify_admin_order(bot, *, header: str, order: dict) -> None:
    """Уведомление админу о заказе. Сбой логируем (только номер заказа и tg_id),
    на выдачу трека не влияет."""
    try:
        tg = order.get("telegram_id")
        tg_str = str(tg) if tg else "—"
        lines = [
            header,
            f"№ {order['order_number']}",
            f"🎧 {order.get('product_title') or '—'}",
            f"💰 {order.get('amount_rub') or 0} ₽",
            f"👤 {order.get('customer_name') or '—'}",
            f"✉️ {order.get('customer_email') or '—'}",
            f"📱 {order.get('customer_phone') or '—'}",
            f"🆔 telegram_id: {tg_str}",
            f"🕐 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}",
        ]
        extra = order.get("extra_line")
        if extra:
            lines.append(extra)
        await bot.send_message(settings.admin_telegram_id, "\n".join(lines))
    except TelegramAPIError:
        logger.exception(
            "admin order notify failed: order=%s tg=%s",
            order.get("order_number"),
            order.get("telegram_id"),
        )


async def _resolve_product_title(
    offer: tuple[str, int, int] | None, title_param: Any
) -> str | None:
    """Название продукта: по каталогу бота при известном оффере, иначе как пришло."""
    if offer is not None and offer[0] == "track":
        track = await db.get_track(offer[1])
        if track is not None:
            return track["title"]
    if offer is not None and offer[0] == "med":
        from app.meditations import get_meditation

        med = get_meditation(offer[1])
        if med is not None:
            return med["title"]
    if title_param:
        return str(title_param).strip()
    return None


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


@router.get("/order-created")
@router.post("/order-created")
async def getcourse_order_created(request: Request) -> JSONResponse:
    """Вебхук «заказ создан в GetCourse» — присылает уведомление админу.

    telegram_id может отсутствовать (заказ не через бота) — уведомление
    всё равно приходит с прочерком.
    """
    payload = await _collect_payload(request)
    order_number = str(
        _pick(payload, ("order_number", "order_id", "deal_id")) or ""
    ).strip()
    logger.info(
        "GetCourse order-created received: order=%s tg=%s",
        order_number or "?",
        _pick(payload, TG_ID_KEYS),
    )
    if not order_number:
        return JSONResponse(
            {"status": "error", "error": "missing_order_number"}, status_code=400
        )

    raw_tg_id = _pick(payload, TG_ID_KEYS)
    try:
        telegram_id = int(raw_tg_id) if raw_tg_id not in (None, "", "0") else None
    except (TypeError, ValueError):
        telegram_id = None

    offer = _extract_offer(_pick(payload, OFFER_ID_KEYS))
    track_id = offer[1] if offer and offer[0] == "track" else None
    offer_id = offer[2] if offer else None
    title_param = _pick(payload, TRACK_TITLE_KEYS)
    product_title = await _resolve_product_title(offer, title_param)
    customer = _extract_customer(payload)

    created = await db.upsert_order_created(
        order_number,
        telegram_id,
        track_id,
        offer_id,
        customer["amount"],
        product_title,
        customer["name"],
        customer["email"],
        customer["phone"],
    )
    if not created:
        return JSONResponse({"status": "duplicate"})

    bot = getattr(request.app.state, "bot", None)
    if bot is not None:
        await _notify_admin_order(
            bot,
            header="🆕 Новый заказ",
            order={
                "order_number": order_number,
                "product_title": product_title,
                "amount_rub": customer["amount"],
                "customer_name": customer["name"],
                "customer_email": customer["email"],
                "customer_phone": customer["phone"],
                "telegram_id": telegram_id,
            },
        )
    return JSONResponse({"status": "ok"})


async def _notify_paid_admin(
    bot, order_number: str, order: Any
) -> None:
    """«✅ Заказ оплачен» — один раз на заказ (paid_notified), со временем
    от создания до оплаты, если событие «создан» приходило раньше."""
    if order is None or not await db.try_mark_paid_notified(order_number):
        return
    extra = None
    try:
        created_at = datetime.fromisoformat(order["created_at"])
        paid_at = datetime.fromisoformat(order["paid_at"])
        delta = paid_at - created_at
        minutes = int(delta.total_seconds() // 60)
        if minutes >= 1:
            extra = f"⏱ оплачен через {minutes // 60} ч {minutes % 60} мин после создания"
    except (TypeError, ValueError, KeyError):
        pass
    await _notify_admin_order(
        bot,
        header="✅ Заказ оплачен",
        order={
            "order_number": order_number,
            "product_title": order["product_title"],
            "amount_rub": order["amount_rub"],
            "customer_name": order["customer_name"],
            "customer_email": order["customer_email"],
            "customer_phone": order["customer_phone"],
            "telegram_id": order["telegram_id"] or None,
            "extra_line": extra,
        },
    )


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
    order_number = (
        order_number
        or f"auto-{telegram_id}-m{med['med_id']}-{int(datetime.now(timezone.utc).timestamp())}"
    )
    order = await db.mark_order_paid(
        order_number, telegram_id, None, med["offer_id"], med["price"],
        product_title=med["title"],
    )
    await _notify_paid_admin(bot, order_number, order)

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
    logger.info(
        "GetCourse webhook received: order=%s tg=%s offer=%s",
        _pick(payload, ("order_number", "order_id", "deal_id")),
        _pick(payload, TG_ID_KEYS),
        _pick(payload, OFFER_ID_KEYS),
    )

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
    customer = _extract_customer(payload)
    order_number = (
        order_number
        or f"auto-{telegram_id}-{track['track_id']}-{int(datetime.now(timezone.utc).timestamp())}"
    )
    order = await db.mark_order_paid(
        order_number,
        telegram_id,
        track["track_id"],
        offer[2] if offer else None,
        customer["amount"] or settings.track_price_rub,
        product_title=track["title"],
        customer_name=customer["name"],
        customer_email=customer["email"],
        customer_phone=customer["phone"],
    )
    await _notify_paid_admin(bot, order_number, order)
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
