import logging

from fastapi import APIRouter, HTTPException, Request

from aiogram.types import Update

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("")
async def telegram_webhook(request: Request) -> dict:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot is disabled")
    from app.config import settings

    if settings.telegram_webhook_secret and request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    ) != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    update = Update.model_validate(await request.json())
    try:
        await request.app.state.dp.feed_update(bot, update)
    except Exception:
        # вебхук всегда отвечает 200 — иначе Telegram ретраит апдейт,
        # очередь растёт, кнопки у пользователя «зависают»
        logger.exception("Error handling update %s", update.update_id)
    return {"ok": True}
