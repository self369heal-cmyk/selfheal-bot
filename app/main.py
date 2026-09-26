import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # импорты внутри lifespan: `from app.main import app` должно работать
    # в окружении с одним лишь fastapi (проверка деплоя)
    from app.admin import router as admin_router
    from app.bot import create_bot, create_dispatcher
    from app.config import settings
    from app.db import init_db
    from app.webhooks import getcourse, telegram

    await init_db()

    app.state.dp = create_dispatcher()

    app.include_router(
        telegram.router,
        prefix=settings.telegram_webhook_path,
        tags=["telegram"],
    )
    app.include_router(
        getcourse.router,
        prefix=settings.getcourse_webhook_path,
        tags=["getcourse"],
    )
    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    if settings.bot_token:
        bot = create_bot()
        app.state.bot = bot
        if settings.public_base_url:
            try:
                await asyncio.wait_for(
                    bot.set_webhook(
                        settings.telegram_webhook_url,
                        drop_pending_updates=True,
                        secret_token=settings.telegram_webhook_secret or None,
                    ),
                    timeout=15,
                )
                logger.info(
                    "Telegram webhook set to %s", settings.telegram_webhook_url
                )
            except Exception:
                logger.exception("Failed to register Telegram webhook")
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
        try:
            await asyncio.wait_for(
                bot.delete_webhook(drop_pending_updates=False), timeout=10
            )
        except Exception:
            logger.exception("Failed to delete Telegram webhook")
        await bot.session.close()


app = FastAPI()
app.title = "SelfHeal Bot"
app.router.lifespan_context = lifespan


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    from app.config import settings

    uvicorn.run(
        "app.main:app", host=settings.webapp_host, port=settings.webapp_port
    )
