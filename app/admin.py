import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/db-dump", response_model=None)
async def db_dump(request: Request):
    """Выгрузка selfheal.db для автоматических бэкапов.

    Требует заголовок X-Backup-Key, равный BACKUP_KEY из окружения.
    Если BACKUP_KEY не задан — эндпоинт отключён.
    """
    if not settings.backup_key or (
        request.headers.get("x-backup-key") != settings.backup_key
    ):
        return JSONResponse({"status": "error"}, status_code=403)
    db_path = Path(settings.database_path)
    if not db_path.exists():
        return JSONResponse(
            {"status": "error", "error": "db_not_found"}, status_code=404
        )
    return FileResponse(db_path, filename="selfheal.db")
