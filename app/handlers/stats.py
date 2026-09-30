import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from app import db
from app.config import settings
from app.meditations import MEDITATIONS_BY_ID

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


def _issue_rank(overview: dict) -> str:
    """Полный рейтинг по выдаче: 12 треков (user_tracks) + медитации (user_meditations)."""
    items = [(r["title"].split(" (")[0], r["cnt"]) for r in overview["track_issue_rank"]]
    items += [
        (f"🎬 {MEDITATIONS_BY_ID[mid]['button']}", cnt)
        for mid, cnt in overview["med_issue_counts"].items()
        if mid in MEDITATIONS_BY_ID
    ]
    # медитации без выдач показываем нулями — рейтинг должен быть полным
    for mid, med in MEDITATIONS_BY_ID.items():
        if mid not in overview["med_issue_counts"]:
            items.append((f"🎬 {med['button']}", 0))
    items.sort(key=lambda x: -x[1])
    return "\n".join(f"  • {name} — {cnt}" for name, cnt in items) or "  —"


def _magnet_lines(rows) -> str:
    return "\n".join(
        f"  • {r['title'].split(' (')[0]} — {r['cnt']}" for r in rows
    ) or "  —"


def render_stats(overview: dict) -> str:
    rt = overview["referrals_total"]
    conv = overview["ref_buyers"]
    pct = f" ({conv / rt * 100:.0f}%)" if rt else ""
    return (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей всего: <b>{overview['users_total']}</b>\n"
        f"🔊 Треков выдано: {overview['tracks_issued']}\n"
        f"🎁 Только бонус (без покупок): {overview['free_only']}\n"
        f"🔗 Реферальных переходов: {overview['referrals_total']}\n"
        f"🔄 Конверсия рефералов в покупки: {conv} из {rt}{pct}\n"
        f"🧾 Заказов всего: {overview['orders_total']}\n"
        f"🛒 Покупок всего: {overview['purchases_total']}\n"
        f"💳 Купили хотя бы один продукт: {overview['buyers']}\n"
        f"💰 Выручка всего: {overview['revenue_total']} ₽\n"
        f"✉️ Сообщений от пользователей: {overview['messages_total']}\n\n"
        f"🏆 <b>Топ-3 продаваемых (по заказам):</b>\n{_track_lines(overview['top_tracks'])}\n\n"
        f"📋 <b>Рейтинг по выдаче (треки + медитации):</b>\n{_issue_rank(overview)}\n\n"
        f"🧲 <b>Чаще пересылают (приход по трек-ссылке):</b>\n{_magnet_lines(overview['track_magnets'])}"
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
