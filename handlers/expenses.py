import logging
from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database


logger = logging.getLogger(__name__)

expenses_router = Router()


# Фиксированный список категорий.
CATEGORIES = {
    "продукты": "🍔 Продукты",
    "коммуналка": "🏠 Коммуналка",
    "транспорт": "🚗 Транспорт",
    "развлечения": "🎬 Развлечения",
    "здоровье": "💊 Здоровье",
    "другое": "📦 Другое",
}


class AddExpense(StatesGroup):
    choosing_members = State()


def _format_amount(amount) -> str:
    """Форматирует сумму без лишних нулей после запятой."""
    value = Decimal(str(amount))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _member_id(member):
    """Достаёт ID участника из словаря или объекта."""
    if isinstance(member, dict):
        return member.get("user_id") or member.get("id")

    return getattr(member, "user_id", None) or getattr(member, "id", None)


def _member_name(member):
    """Достаёт отображаемое имя участника."""
    if isinstance(member, dict):
        return (
            member.get("display_name")
            or member.get("name")
            or member.get("full_name")
            or member.get("username")
            or str(_member_id(member))
        )

    return (
        getattr(member, "display_name", None)
        or getattr(member, "name", None)
        or getattr(member, "full_name", None)
        or getattr(member, "username", None)
        or str(_member_id(member))
    )


def _get_members_from_state(data):
    """Восстанавливает список участников из данных FSM."""
    return data.get("members_json", [])


def _build_members_keyboard(members, selected):
    """Создаёт клавиатуру выбора участников."""
    selected_set = {int(user_id) for user_id in selected}

    buttons = []

    for member in members:
        user_id = _member_id(member)
        if user_id is None:
            continue

        name = escape(_member_name(member))

        if int(user_id) in selected_set:
            text = f"✅ {name}"
        else:
            text = f"☐ {name}"

        buttons.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"toggle_{user_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="✅ Все",
                callback_data="select_all",
            ),
            InlineKeyboardButton(
                text="💾 Готово",
                callback_data="save",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _selection_text_with_category(members, selected, amount, category):
    """Формирует текст выбора участников с категорией."""
    selected_set = {int(user_id) for user_id in selected}
    selected_members = [
        member
        for member in members
        if _member_id(member) is not None
        and int(_member_id(member)) in selected_set
    ]

    amount_text = _format_amount(amount)
    category_text = CATEGORIES.get(category, category)

    if not selected_members:
        return (
            f"Трата: <b>{amount_text} ₽</b>\n"
            f"Категория: <b>{escape(category_text)}</b>\n\n"
            "Выбери хотя бы одного участника."
        )

    share = Decimal(str(amount)) / len(selected_members)
    share_text = _format_amount(share)

    names = ", ".join(
        escape(_member_name(member))
        for member in selected_members
    )

    return (
        f"Трата: <b>{amount_text} ₽</b>\n"
        f"Категория: <b>{escape(category_text)}</b>\n"
        f"Выбраны: {names}\n"
        f"На каждого: <b>{share_text} ₽</b>"
    )


@expenses_router.message(Command("add"))
async def add_expense_command(
    message: Message,
    command: CommandObject,
    state: FSMContext,
):
    """Начинает добавление новой траты."""
    try:
        space = await database.get_user_space(message.from_user.id)

        if not space:
            await message.answer(
                "Сначала /create или /join КОД",
                parse_mode="HTML",
            )
            return

        args = (command.args or "").strip()

        if not args:
            await message.answer(
                "Формат: /add СУММА КАТЕГОРИЯ\n"
                "Пример: /add 500 продукты\n\n"
                "Доступные категории: продукты, коммуналка, транспорт, "
                "развлечения, здоровье, другое",
                parse_mode="HTML",
            )
            return

        parts = args.split(maxsplit=1)

        if len(parts) != 2:
            await message.answer(
                "Формат: /add СУММА КАТЕГОРИЯ\n"
                "Пример: /add 500 продукты\n\n"
                "Доступные категории: продукты, коммуналка, транспорт, "
                "развлечения, здоровье, другое",
                parse_mode="HTML",
            )
            return

        amount_raw, category = parts
        category = category.strip().lower()

        try:
            amount = Decimal(amount_raw.replace(",", "."))
        except (InvalidOperation, ValueError):
            await message.answer(
                "Сумма должна быть числом, например: 500 или 500.50.",
                parse_mode="HTML",
            )
            return

        if amount <= 0:
            await message.answer(
                "Сумма должна быть больше нуля.",
                parse_mode="HTML",
            )
            return

        if category not in CATEGORIES:
            await message.answer(
                "Неизвестная категория.\n\n"
                "Доступные категории: продукты, коммуналка, транспорт, "
                "развлечения, здоровье, другое",
                parse_mode="HTML",
            )
            return

        members = await database.get_space_members_with_names(space["id"])

        if not members:
            await message.answer(
                "В пространстве пока нет участников.",
                parse_mode="HTML",
            )
            return

        members_json = [
            {
                "user_id": int(_member_id(member)),
                "display_name": str(_member_name(member)),
            }
            for member in members
            if _member_id(member) is not None
        ]

        await state.update_data(
            amount=str(amount),
            category=category,
            selected_member_ids=[],
            members_json=members_json,
        )
        await state.set_state(AddExpense.choosing_members)

        await message.answer(
            _selection_text_with_category(
                members_json,
                [],
                amount,
                category,
            ),
            reply_markup=_build_members_keyboard(members_json, []),
            parse_mode="HTML",
        )

    except Exception:
        logger.exception("Ошибка при начале добавления траты")
        await message.answer(
            "Не удалось начать добавление траты. Попробуй ещё раз.",
            parse_mode="HTML",
        )


@expenses_router.callback_query(
    AddExpense.choosing_members,
    lambda callback: callback.data and callback.data.startswith("toggle_"),
)
async def toggle_member(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Переключает участника в списке выбранных."""
    try:
        data = await state.get_data()

        amount = Decimal(str(data["amount"]))
        category = data["category"]
        selected = [int(user_id) for user_id in data.get("selected_member_ids", [])]
        members = _get_members_from_state(data)

        user_id = int(callback.data.removeprefix("toggle_"))

        member_ids = {
            int(_member_id(member))
            for member in members
            if _member_id(member) is not None
        }

        if user_id not in member_ids:
            await callback.answer("Участник не найден.", show_alert=True)
            return

        if user_id in selected:
            selected.remove(user_id)
        else:
            selected.append(user_id)

        await state.update_data(selected_member_ids=selected)

        await callback.message.edit_text(
            _selection_text_with_category(
                members,
                selected,
                amount,
                category,
            ),
            reply_markup=_build_members_keyboard(members, selected),
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception:
        logger.exception("Ошибка при выборе участника")
        await callback.answer(
            "Не удалось изменить выбор.",
            show_alert=True,
        )


@expenses_router.callback_query(
    AddExpense.choosing_members,
    lambda callback: callback.data == "select_all",
)
async def select_all_members(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Выбирает всех участников пространства."""
    try:
        data = await state.get_data()

        amount = Decimal(str(data["amount"]))
        category = data["category"]
        members = _get_members_from_state(data)

        selected = [
            int(_member_id(member))
            for member in members
            if _member_id(member) is not None
        ]

        await state.update_data(selected_member_ids=selected)

        await callback.message.edit_text(
            _selection_text_with_category(
                members,
                selected,
                amount,
                category,
            ),
            reply_markup=_build_members_keyboard(members, selected),
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception:
        logger.exception("Ошибка при выборе всех участников")
        await callback.answer(
            "Не удалось выбрать всех участников.",
            show_alert=True,
        )


@expenses_router.callback_query(
    AddExpense.choosing_members,
    lambda callback: callback.data == "save",
)
async def save_expense(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Сохраняет трату с выбранными участниками."""
    try:
        data = await state.get_data()

        selected = [
            int(user_id)
            for user_id in data.get("selected_member_ids", [])
        ]

        if not selected:
            await callback.answer(
                "Выбери хотя бы одного",
                show_alert=True,
            )
            return

        amount = Decimal(str(data["amount"]))
        category = data["category"]

        space = await database.get_user_space(callback.from_user.id)

        if not space:
            await state.clear()
            await callback.message.edit_text(
                "Сначала /create или /join КОД",
                parse_mode="HTML",
            )
            await callback.answer()
            return

        await database.add_expense(
            space["id"],
            payer_id=callback.from_user.id,
            amount=amount,
            category=category,
            description=None,
            member_ids=selected,
        )

        share = amount / len(selected)
        amount_text = _format_amount(amount)
        share_text = _format_amount(share)

        await state.clear()

        await callback.message.edit_text(
            f"✅ Трата {amount_text} ₽ на «{escape(category)}» записана.\n"
            f"Поровну на {len(selected)} чел. — по {share_text} ₽.",
            parse_mode="HTML",
        )
        await callback.answer()

    except Exception:
        logger.exception("Ошибка при сохранении траты")
        await callback.answer(
            "Не удалось сохранить трату. Попробуй ещё раз.",
            show_alert=True,
        )


@expenses_router.message(Command("balance"))
@expenses_router.message(F.text == "📊 Баланс")
async def balance_command(message: Message):
    """Показывает текущие взаимные долги."""
    try:
        space = await database.get_user_space(message.from_user.id)

        if not space:
            await message.answer(
                "Сначала /create или /join КОД",
                parse_mode="HTML",
            )
            return

        debts = await database.get_balance(space["id"])

        if not debts:
            await message.answer(
                "Все в расчёте! 🎉",
                parse_mode="HTML",
            )
            return

        lines = ["💸 Кто кому должен:", ""]

        # get_balance возвращает список кортежей:
        # (debtor_id, debtor_name, creditor_id, creditor_name, amount)
        for debt in debts:
            if len(debt) == 5:
                _, from_name, _, to_name, amount = debt
            else:
                from_name = "Участник"
                to_name = "Участник"
                amount = 0

            lines.append(
                f"• {escape(str(from_name))} → "
                f"{escape(str(to_name))}: "
                f"{_format_amount(amount)} ₽"
            )

        await message.answer(
            "\n".join(lines),
            parse_mode="HTML",
        )

    except Exception:
        logger.exception("Ошибка при получении баланса")
        await message.answer(
            "Не удалось получить баланс. Попробуй ещё раз.",
            parse_mode="HTML",
        )


@expenses_router.message(Command("history"))
@expenses_router.message(F.text == "📜 История")
async def history_command(message: Message):
    """Показывает последние 10 расходов."""
    try:
        space = await database.get_user_space(message.from_user.id)

        if not space:
            await message.answer(
                "Сначала /create или /join КОД",
                parse_mode="HTML",
            )
            return

        history = await database.get_history(
            space["id"],
            limit=10,
        )

        if not history:
            await message.answer(
                "📜 Последние траты:\n\nПока трат нет.",
                parse_mode="HTML",
            )
            return

        lines = ["📜 Последние траты:", ""]

        for expense in history:
            amount = expense["amount"]
            category = expense["category"]
            payer_name = expense["payer_name"]
            date = expense["created_at"]

            # Берём только дату в формате ДД.ММ.
            if hasattr(date, "strftime"):
                date_text = date.strftime("%d.%m")
            else:
                date_text = str(date)
                if " " in date_text:
                    date_text = date_text.split(" ", 1)[0]
                if "T" in date_text:
                    date_text = date_text.split("T", 1)[0]

                parts = date_text.split("-")
                if len(parts) == 3:
                    date_text = f"{parts[2]}.{parts[1]}"

            lines.append(
                f"• {_format_amount(amount)} ₽ — "
                f"{escape(str(category))} "
                f"({escape(str(payer_name))}) — "
                f"{escape(date_text)}"
            )

        await message.answer(
            "\n".join(lines),
            parse_mode="HTML",
        )

    except Exception:
        logger.exception("Ошибка при получении истории")
        await message.answer(
            "Не удалось получить историю. Попробуй ещё раз.",
            parse_mode="HTML",
        )