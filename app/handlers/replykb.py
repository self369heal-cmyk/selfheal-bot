"""Reply-клавиатура 2x2 внизу экрана (закрепляется в /start).

Кнопки открывают те же разделы, что и inline-меню — переиспользуются
общие view-функции (purchases_view / referral_view / catalog_view),
отдельной параллельной логики нет. Роутер включён до inbox (catch-all),
поэтому тексты кнопок не улетают админу как «свободные сообщения».
"""

import logging

from aiogram import F, Router
from aiogram.types import Message

from app import db
from app.handlers import inbox
from app.handlers.catalog import catalog_view
from app.handlers.purchases import purchases_view
from app.handlers.referral import referral_view
from app.keyboards import (
    BTN_CATALOG,
    BTN_CATALOG_LEGACY,
    BTN_PURCHASES,
    BTN_REFERRALS,
    BTN_REFERRALS_LEGACY,
    BTN_REVIEW,
)

logger = logging.getLogger(__name__)

router = Router()

REVIEW_PROMPT = "Напишите ваш отзыв или вопрос — я передам его Владемиру 💬"


@router.message(F.text == BTN_PURCHASES)
async def reply_purchases(message: Message) -> None:
    text, kb = await purchases_view(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.message(F.text.in_({BTN_CATALOG, BTN_CATALOG_LEGACY}))
async def reply_catalog(message: Message) -> None:
    text, kb = await catalog_view(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.message(F.text.in_({BTN_REFERRALS, BTN_REFERRALS_LEGACY}))
async def reply_referrals(message: Message) -> None:
    text, kb = await referral_view(message.from_user.id, message.bot)
    await message.answer(text, reply_markup=kb)


@router.message(F.text == BTN_REVIEW)
async def reply_review(message: Message) -> None:
    # следующее свободное сообщение пользователя уйдёт админу с пометкой «отзыв» —
    # флаг снимается после первой пересылки (см. inbox.forward_to_admin)
    inbox.AWAITING_REVIEW.add(message.from_user.id)
    await message.answer(REVIEW_PROMPT)
