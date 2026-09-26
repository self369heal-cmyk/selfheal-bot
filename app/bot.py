from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from app.config import settings
from app.handlers import (
    backupdb,
    catalog,
    getfileid,
    menu,
    purchases,
    referral,
    start,
)


def create_bot() -> Bot:
    session = None
    if settings.telegram_api_base:
        api_base = settings.telegram_api_base.rstrip("/")
        session = AiohttpSession(
            api=TelegramAPIServer(
                base=f"{api_base}/bot{{token}}/{{method}}",
                file=f"{api_base}/file/bot{{token}}/{{path}}",
            )
        )
    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(referral.router)
    dp.include_router(purchases.router)
    dp.include_router(menu.router)
    dp.include_router(getfileid.router)
    dp.include_router(backupdb.router)
    return dp
