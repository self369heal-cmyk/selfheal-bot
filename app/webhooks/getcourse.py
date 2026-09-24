import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("")
async def getcourse_webhook(request: Request) -> dict:
    """Заглушка приёма сигнала оплаты от GetCourse.

    Пока только логирует входящие данные (JSON или form-data).
    Полная логика выдачи трека будет добавлена на следующем шаге.
    """
    payload: Any
    if "application/json" in request.headers.get("content-type", ""):
        payload = await request.json()
    else:
        payload = dict(await request.form())
    logger.info("GetCourse webhook received: %s", payload)
    return {"status": "ok"}
