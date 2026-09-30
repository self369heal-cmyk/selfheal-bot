import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from urllib.parse import quote

from app import db
from app.config import settings
from app.handlers.referral import send_track
from app.keyboards import BACK_LABEL, CB_MENU
from app.subscription import require_subscription

logger = logging.getLogger(__name__)

router = Router()

TRACK_PRICE = 900

# постер каталога КИТ — file_id боевого бота (assets/catalog-kit.png)
CATALOG_PHOTO_FILE_ID = "AgACAgQAAxkDAAIHc2q9Dr31zuLfdj76rysaffgTOzlXAAKTD2sbQEftUYf4hHGg_jLjAQADAgADeQADPQQ"

# короткие названия кнопок-разделителей (неактивные) и треков — утверждены заказчиком
SECTION_SHORT = {
    "emotions": "😔 Эмоции и психика",
    "energy": "☀️ Энергия и деньги",
    "body": "💪 Исцеление тела",
}
SECTION_ORDER = ("emotions", "energy", "body")
TRACK_SHORT = {
    1: "АнтиСтресс",
    2: "Исцеление эмоций",
    3: "Хороший сон",
    4: "Хорошее настроение",
    5: "Концентрация",
    6: "Энергия",
    7: "Деньги и изобилие",
    8: "Связь с Душой",
    9: "Здоровая спина",
    10: "Здоровая голова",
    11: "ЖКТ и пищеварение",
    12: "Иммунитет",
}

# track_id -> slug страницы оплаты GetCourse (edu.selfheal369.ru/{slug})
TRACK_PAY_SLUGS = {
    1: "antistress",
    2: "emotions",
    3: "sleep",
    4: "mood",
    5: "focus",
    6: "energy",
    7: "money",
    8: "soul",
    9: "spine",
    10: "head",
    11: "digestion",
    12: "immunity",
}

# разделы каталога — названия утверждены заказчиком
SECTIONS: dict[str, str] = {
    "emotions": "😔 Эмоции, психика и расслабление (убрать тревогу, апатию, обиды)",
    "energy": "☀️ Состояние, энергия, деньги и реализация",
    "body": "💪 Исцеление тела",
}


async def _catalog_to_message(message, text: str, kb: InlineKeyboardMarkup) -> None:
    """Отрисовать каталог: сообщение с фото — меняем подпись,
    текстовое — заменяем фото-сообщением (единый экран сохраняется)."""
    if message.photo:
        await message.edit_caption(caption=text, reply_markup=kb)
    else:
        await message.delete()
        await message.answer_photo(
            photo=CATALOG_PHOTO_FILE_ID, caption=text, reply_markup=kb
        )


async def edit_card(callback: CallbackQuery, text: str, kb=None) -> None:
    """Править экран: фото-сообщение → caption, текстовое → edit_text."""
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)


async def catalog_view(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Единый экран каталога: весь список текстом + кнопки треков с разделителями.
    Купленные треки помечаются ✅ и в тексте, и на кнопке."""
    tracks = await db.get_all_tracks()
    owned = {r["track_id"] for r in await db.get_user_tracks(telegram_id)}

    lines: list[str] = [
        "🧬 <b>Коды Исцеления Тела (КИТ)</b>: исцеляющие аудиотреки.",
        "",
        "Они улучшают самочувствие, снимают боли и напряжение, "
        "успокаивают психику и убирают стресс.",
        "",
        "<b>3 раздела и 12 треков</b>",
        "",
    ]
    for sec in SECTION_ORDER:
        lines.append(f"<b>{SECTIONS[sec]}</b>")
        for t in tracks:
            if t["section"] == sec:
                mark = "✅ " if t["track_id"] in owned else ""
                main, _, rest = t["title"].partition(" (")
                rest = f" ({rest}" if rest else ""
                lines.append(f"{mark}{t['track_id']}. <b>{main}</b>{rest}")
        lines.append("")
    text = "\n".join(lines).rstrip()

    rows: list[list[InlineKeyboardButton]] = []
    for sec in SECTION_ORDER:
        rows.append(
            [InlineKeyboardButton(text=SECTION_SHORT[sec], callback_data="noop")]
        )
        pair: list[InlineKeyboardButton] = []
        for t in tracks:
            if t["section"] != sec:
                continue
            mark = "✅ " if t["track_id"] in owned else ""
            pair.append(
                InlineKeyboardButton(
                    text=f"{mark}{t['track_id']}. {TRACK_SHORT.get(t['track_id'], t['title'])}",
                    callback_data=f"track:{t['track_id']}",
                )
            )
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
    rows.append([InlineKeyboardButton(text=BACK_LABEL, callback_data=CB_MENU)])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def track_card_text(track, free_available: bool, owned: bool) -> str:
    price = "бесплатно для вас" if free_available else f"{TRACK_PRICE} ₽"
    description = track["description"] or ""
    # первая строка описания — эмодзи-заголовок caption, в карточке он дублирует название
    body = description.split("\n", 1)[1].lstrip() if "\n" in description else description
    text = (
        f"🔊 <b>{track['title']}</b>\n"
        f"Раздел: {SECTIONS.get(track['section'], track['section'])}\n"
        f"Для чего: {body}\n"
        f"Цена: {price}"
    )
    if owned:
        text += "\n\n🔊 Этот трек уже у вас. Найдите его в разделе «💳 Мои покупки»."
    return text


def pay_url(track, telegram_id: int) -> str:
    return settings.getcourse_pay_url_template.format(
        track_id=track["track_id"],
        track_slug=TRACK_PAY_SLUGS.get(track["track_id"], ""),
        telegram_id=telegram_id,
        track_title=quote(track["title"]),
    )


def track_kb(
    track,
    free_available: bool,
    owned: bool,
    telegram_id: int,
    bonus_available: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    tid = track["track_id"]
    if not owned:
        if bonus_available:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🎁 Забрать бонус-трек",
                        callback_data=f"bonus:{tid}",
                        style="success",
                    )
                ]
            )
        if free_available:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🎁 Забрать бесплатно",
                        callback_data=f"free:{tid}",
                        style="success",
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"💳 Купить за {TRACK_PRICE} ₽",
                        url=pay_url(track, telegram_id),
                        style="success",
                    )
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🎁 Пригласить 3х друзей и получить бонусом",
                        callback_data="referral",
                    )
                ]
            )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад к каталогу",
                callback_data="catalog",
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "noop")
async def noop_button(callback: CallbackQuery) -> None:
    # разделитель-заголовок: только гасим «часики»
    await callback.answer()


@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery) -> None:
    text, kb = await catalog_view(callback.from_user.id)
    await _catalog_to_message(callback.message, text, kb)


@router.callback_query(F.data.startswith("sec:"))
async def show_section(callback: CallbackQuery) -> None:
    # старые экраны с кнопками разделов — ведём в общий каталог
    text, kb = await catalog_view(callback.from_user.id)
    await _catalog_to_message(callback.message, text, kb)


@router.callback_query(F.data.startswith("track:"))
async def show_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    user = await db.get_user(callback.from_user.id)
    free_available = bool(user) and not user["got_free_track"]
    owned = await db.user_has_track(callback.from_user.id, track_id)
    bonus_available = False
    if user and not free_available:
        earned = await db.count_referrals(callback.from_user.id) // 3
        bonus_available = earned + (user["promo_bonus"] or 0) > (user["bonus_claimed"] or 0)
    await edit_card(
        callback,
        track_card_text(track, free_available, owned),
        track_kb(
            track, free_available, owned, callback.from_user.id, bonus_available
        ),
    )


async def _deliver_free_track(callback: CallbackQuery, user, track) -> None:
    """Выдать/дослать бесплатный трек или отказать по «уже использован». Подписка проверена снаружи."""
    track_id = track["track_id"]
    if user["got_free_track"]:
        if await db.user_has_track(callback.from_user.id, track_id):
            # повтор после transient-ретрая: трек уже выдан — досылаем файл
            if track["file_id"]:
                await send_track(callback.message, callback.from_user.id, track)
            return
        await callback.answer(
            "Бесплатный трек уже использован, этот можно купить 🙌",
            show_alert=True,
        )
        return

    await db.mark_got_free_track(callback.from_user.id)
    await db.add_user_track(callback.from_user.id, track_id)
    logger.info("User %s claimed free track %s", callback.from_user.id, track_id)

    await edit_card(
        callback,
        f"🎁 <b>{track['title']}</b>: ваш подарок!\n\n"
        "Трек придёт следующим сообщением. Желательно перед запуском трека "
        "<b>выбрать намерение и свой желаемый результат</b>. "
        "Слушайте на любой комфортной громкости и любое количество времени до результата. "
        "Наушники не обязательно, можно слушать из телефона на минимальной громкости.\n\n"
        "Подробные рекомендации по прослушиванию в разделе «📖 Как слушать КИТ».",
    )
    if track["file_id"]:
        await send_track(callback.message, callback.from_user.id, track)


@router.callback_query(F.data.startswith("free:"))
async def claim_free_track(callback: CallbackQuery) -> None:
    track_id = int(callback.data.split(":", 1)[1])
    user = await db.get_user(callback.from_user.id)
    if user is None:
        await callback.answer("Нажмите /start для регистрации", show_alert=True)
        return
    track = await db.get_track(track_id)
    if track is None:
        await callback.answer("Трек не найден", show_alert=True)
        return
    if not await require_subscription(callback, track_id, "free"):
        return
    await _deliver_free_track(callback, user, track)

