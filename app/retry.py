import asyncio
import logging
import sqlite3
from typing import Awaitable, Callable, TypeVar

from aiogram.exceptions import TelegramNetworkError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# временные сбои: залоченная/недоступная SQLite, таймауты и сетевые ошибки Bot API
TRANSIENT_ERRORS = (
    sqlite3.OperationalError,
    asyncio.TimeoutError,
    TelegramNetworkError,
)


async def retry_transient(
    fn: Callable[[], Awaitable[T]], attempts: int = 3, delay: float = 0.4
) -> T:
    """Повторяет вызов при transient-ошибках; прочие исключения летят сразу."""
    for attempt in range(attempts):
        try:
            return await fn()
        except TRANSIENT_ERRORS:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(delay * (attempt + 1))
            logger.info(
                "transient error, retry %s/%s", attempt + 2, attempts,
                exc_info=True,
            )
    raise AssertionError("unreachable")
