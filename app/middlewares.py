import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)

# Повторное нажатие той же кнопки тем же пользователем в пределах
# этого окна игнорируется (предохранитель от дабл-кликов и ретраев).
DEBOUNCE_SECONDS = 1.5


class CallbackGuardMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last: dict[tuple[int, str], float] = {}

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        # отвечаем на callback сразу — гасим «часики» у кнопки,
        # не дожидаясь основной работы хендлера
        try:
            await event.answer()
        except Exception:
            logger.debug("callback.answer() failed", exc_info=True)

        if event.from_user is None:
            return await handler(event, data)

        key = (event.from_user.id, event.data or "")
        now = time.monotonic()
        if now - self._last.get(key, 0) < DEBOUNCE_SECONDS:
            return None
        self._last[key] = now

        return await handler(event, data)
