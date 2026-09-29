"""Промокоды: /promo → пользователь вводит код → +1 бонус-трек на выбор.

Ожидание кода — in-memory set PROMO_AWAITING (как AWAITING_REVIEW в inbox):
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

# telegram_id пользователей, вызвавших /promo — следующий текст трактуется как код
PROMO_AWAITING: set[int] = set()

PROMO_ASK = "Введите промокод 🔑"
PROMO_OK = (
    "🎁 Промокод принят! У вас открыт бонус-трек — выберите его в каталоге:"
)
PROMO_BAD = (
    "Такого промокода нет, он уже использован или закончился 😔 "
    "Проверьте написание и попробуйте ещё раз: /promo"
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
    PROMO_AWAITING.add(message.from_user.id)
    await message.answer(PROMO_ASK)


@router.message(
    F.text,
    lambda m: m.from_user is not None
    and m.from_user.id in PROMO_AWAITING
    and not m.text.startswith("/"),
)
async def promo_code_input(message: Message) -> None:
    PROMO_AWAITING.discard(message.from_user.id)
    if await db.use_promo(message.from_user.id, message.text):
        logger.info("User %s used promo code", message.from_user.id)
        await message.answer(PROMO_OK, reply_markup=open_catalog_kb())
    else:
        await message.answer(PROMO_BAD)


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
