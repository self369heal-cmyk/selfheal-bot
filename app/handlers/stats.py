import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from app import db
from app.config import settings

logger = logging.getLogger(__name__)

router = Router()

MSK = ZoneInfo("Europe/Moscow")
DIGEST_HOUR = 9


def _is_admin(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id == settings.admin_telegram_id
    )


def _track_lines(rows) -> str:
    lines = []
    for row in rows:
        title = row["title"].split(" (")[0]
        lines.append(f"  • {title} — {row['cnt']}")
    return "\n".join(lines) or "  —"


def render_stats(overview: dict) -> str:
    return (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей всего: <b>{overview['users_total']}</b>\n"
        f"🎁 Только бонус (без покупок): {overview['free_only']}\n"
        f"💳 Купили хотя бы один трек: {overview['buyers']}\n"
        f"🧾 Заказов всего: {overview['orders_total']}\n"
        f"💰 Выручка всего: {overview['revenue_total']} ₽\n"
        f"🔊 Треков выдано: {overview['tracks_issued']}\n"
        f"🔗 Реферальных переходов: {overview['referrals_total']}\n"
        f"✉️ Сообщений от пользователей: {overview['messages_total']}\n\n"
        f"🏆 <b>Топ-3 продаваемых:</b>\n{_track_lines(overview['top_tracks'])}\n\n"
        f"📉 <b>Наименее популярные:</b>\n{_track_lines(overview['bottom_tracks'])}"
    )


def render_daily(stats: dict) -> str:
    return (
        "📅 <b>Сводка за сутки</b>\n\n"
        f"👥 Новых пользователей: {stats['new_users']}\n"
        f"🧾 Покупок: {stats['orders']}\n"
        f"💰 Выручка: {stats['revenue']} ₽\n"
        f"🔗 Новых реферальных переходов: {stats['new_referrals']}\n"
        f"✉️ Сообщений от пользователей: {stats['new_messages']}"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message):
        return
    overview = await db.get_stats_overview()
    await message.answer(render_stats(overview))


async def send_daily_digest(bot: Bot) -> None:
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    stats = await db.get_daily_stats(since)
    await bot.send_message(settings.admin_telegram_id, render_daily(stats))


async def _digest_loop(bot: Bot) -> None:
    while True:
        now = datetime.now(MSK)
        next_run = now.replace(hour=DIGEST_HOUR, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            await send_daily_digest(bot)
        except Exception:
            logger.exception("Daily digest send failed")


def start_digest_task(bot: Bot) -> asyncio.Task:
    return asyncio.create_task(_digest_loop(bot))
