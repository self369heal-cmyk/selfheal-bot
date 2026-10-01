"""Промокоды: /promo → пользователь вводит код → +1 бонус-трек на выбор.

Ожидание кода — флаг users.promo_awaiting в БД (переживает рестарт бота):
снимается после первой попытки. Роутер стоит после replykb (reply-кнопки
работают и во время ожидания кода) и до inbox (свободный текст в режиме
ожидания не улетает админу как обычное сообщение).

Админ-команды (только admin_telegram_id):
  /promo_new КОД [лимит] — создать промокод (без лимита = безлимитный)
  /promo_del КОД — удалить
  /promo_list — список с использованием
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app import db
from app.config import settings
from app.keyboards import open_catalog_kb

logger = logging.getLogger(__name__)

router = Router()

PROMO_ASK = "Введите промокод 🔑"
PROMO_OK = (
    "🎁 Промокод принят! У вас открыт бонус-трек — выберите его в каталоге:"
)
PROMO_MISSING = (
    "Такого промокода нет 😔 Проверьте написание и попробуйте ещё раз: /promo"
)
PROMO_USED = "Вы уже использовали этот промокод — он действует один раз."
PROMO_EXHAUSTED = (
    "У этого промокода закончились активации 😔 "
    "Проверьте написание или попробуйте другой: /promo"
)


def _is_admin(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id == settings.admin_telegram_id
    )


@router.message(Command("promo"))
async def cmd_promo(message: Message) -> None:
    if await db.get_user(message.from_user.id) is None:
        await message.answer("Нажмите /start для регистрации")
        return
    await db.set_promo_awaiting(message.from_user.id, True)
    await message.answer(PROMO_ASK)


async def _awaiting_code(m: Message) -> bool:
    return (
        m.from_user is not None
        and m.text is not None
        and not m.text.startswith("/")
        and await db.is_promo_awaiting(m.from_user.id)
    )


@router.message(F.text, _awaiting_code)
async def promo_code_input(message: Message) -> None:
    # атомарное поглощение: из двух сообщений подряд код принимает только первое
    if not await db.claim_promo_input(message.from_user.id):
        return
    status = await db.use_promo(message.from_user.id, message.text or "")
    if status == "ok":
        logger.info("User %s used promo code", message.from_user.id)
        await message.answer(PROMO_OK, reply_markup=open_catalog_kb())
    else:
        logger.info(
            "User %s promo rejected: %s", message.from_user.id, status
        )
        await message.answer(
            {
                "missing": PROMO_MISSING,
                "already_used": PROMO_USED,
                "exhausted": PROMO_EXHAUSTED,
            }[status]
        )


@router.message(Command("promo_new"))
async def cmd_promo_new(message: Message, command: CommandObject) -> None:
    if not _is_admin(message):
        return
    args = (command.args or "").split()
    if not args:
        await message.answer("Формат: /promo_new КОД [лимит_использований]")
        return
    code = args[0]
    max_uses: int | None = None
    if len(args) > 1:
        try:
            max_uses = int(args[1])
            if max_uses <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Лимит должен быть положительным числом")
            return
    if await db.add_promo_code(code, max_uses):
        limit_text = f"лимит {max_uses}" if max_uses else "без лимита"
        await message.answer(f"✅ Промокод <code>{code.upper()}</code> создан ({limit_text}).")
    else:
        await message.answer(f"Промокод <code>{code.upper()}</code> уже существует.")


@router.message(Command("promo_del"))
async def cmd_promo_del(message: Message, command: CommandObject) -> None:
    if not _is_admin(message):
        return
    code = (command.args or "").strip()
    if not code:
        await message.answer("Формат: /promo_del КОД")
        return
    if await db.delete_promo_code(code):
        await message.answer(f"🗑 Промокод <code>{code.upper()}</code> удалён.")
    else:
        await message.answer(f"Промокод <code>{code.upper()}</code> не найден.")


@router.message(Command("promo_list"))
async def cmd_promo_list(message: Message) -> None:
    if not _is_admin(message):
        return
    rows = await db.list_promo_codes()
    if not rows:
        await message.answer("Промокодов нет. Создайте: /promo_new КОД [лимит]")
        return
    lines = ["🔑 <b>Промокоды:</b>"]
    for r in rows:
        limit = str(r["max_uses"]) if r["max_uses"] is not None else "∞"
        lines.append(f"  • <code>{r['code']}</code> — {r['used_count']}/{limit}")
    await message.answer("\n".join(lines))
