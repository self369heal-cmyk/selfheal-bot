from fastapi import APIRouter, HTTPException, Request

from aiogram.types import Update

router = APIRouter()


@router.post("")
async def telegram_webhook(request: Request) -> dict:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot is disabled")
    update = Update.model_validate(await request.json())
    await request.app.state.dp.feed_update(bot, update)
    return {"ok": True}
