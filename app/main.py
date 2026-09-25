import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.bot import create_bot, create_dispatcher
from app.config import settings
from app.db import init_db
from app.webhooks import getcourse, telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    app.state.dp = create_dispatcher()

    if settings.bot_token:
        bot = create_bot()
        app.state.bot = bot
        if settings.public_base_url:
            await bot.set_webhook(
                settings.telegram_webhook_url, drop_pending_updates=True
            )
            logger.info(
                "Telegram webhook set to %s", settings.telegram_webhook_url
            )
        else:
            logger.warning(
                "WEBHOOK_BASE_URL is not set — "
                "Telegram webhook was not registered"
            )
    else:
        logger.warning("BOT_TOKEN is not set — Telegram bot is disabled")

    yield

    bot = getattr(app.state, "bot", None)
    if bot is not None:
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()


app = FastAPI(title="SelfHeal Bot", lifespan=lifespan)
app.include_router(
    telegram.router, prefix=settings.telegram_webhook_path, tags=["telegram"]
)
app.include_router(
    getcourse.router, prefix=settings.getcourse_webhook_path, tags=["getcourse"]
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", host=settings.webapp_host, port=settings.webapp_port
    )
