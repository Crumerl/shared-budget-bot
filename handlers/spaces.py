import secrets

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import (
    add_member,
    code_exists,
    count_members,
    create_space,
    get_space_by_code,
    get_space_members_with_names,
    get_user_space,
    remove_member,
)

spaces_router = Router()

MAX_MEMBERS = 5
INVITE_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class CreateSpace(StatesGroup):
    waiting_for_title = State()


async def generate_invite_code() -> str:
    while True:
        code = "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(6))
        try:
            if not await code_exists(code):
                return code
        except Exception:
            raise


@spaces_router.message(Command("create"))
async def create_space_handler(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id

    try:
        space = await get_user_space(user_id)
    except Exception:
        await message.answer("Не удалось проверить пространство. Попробуй ещё раз.")
        return

    if space:
        await message.answer(
            f"Ты уже в пространстве «{space['title']}». Сначала /leave."
        )
        return

    await state.set_state(CreateSpace.waiting_for_title)
    await message.answer("Напиши название пространства (от 1 до 50 символов).")


@spaces_router.message(CreateSpace.waiting_for_title)
async def process_space_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()

    if not 1 <= len(title) <= 50:
        await message.answer("Название должно быть от 1 до 50 символов.")
        return

    user_id = message.from_user.id

    try:
        space = await get_user_space(user_id)
    except Exception:
        await message.answer("Не удалось проверить пространство. Попробуй ещё раз.")
        return

    if space:
        await state.clear()
        await message.answer(
            f"Ты уже в пространстве «{space['title']}». Сначала /leave."
        )
        return

    try:
        code = await generate_invite_code()
        space_id = await create_space(title, code, user_id)
        await add_member(
            space_id,
            user_id,
            display_name=message.from_user.first_name,
        )
    except Exception:
        await message.answer("Не удалось создать пространство. Попробуй ещё раз.")
        return

    await state.clear()

    try:
        bot = await message.bot.me()
        bot_username = bot.username or ""
    except Exception:
        bot_username = ""

    await message.answer(
        f"✅ Пространство «{title}» создано!\n\n"
        f"🔑 Код: <code>{code}</code>\n"
        f"🔗 Ссылка: https://t.me/{bot_username}?start=join_{code}\n\n"
        "Максимум 5 человек.",
        parse_mode="HTML",
    )


@spaces_router.message(Command("join"))
async def join_handler(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id

    try:
        space = await get_user_space(user_id)
    except Exception:
        await message.answer("Не удалось проверить пространство. Попробуй ещё раз.")
        return

    if space:
        await message.answer(
            f"Ты уже в пространстве «{space['title']}». Сначала /leave."
        )
        return

    if not command.args:
        await message.answer("Напиши код: /join ABC123")
        return

    await join_by_code(message, command.args)


async def join_by_code(message: Message, code: str) -> None:
    code = code.strip().upper()
    user_id = message.from_user.id

    try:
        space = await get_space_by_code(code)
    except Exception:
        await message.answer("Не удалось найти пространство. Попробуй ещё раз.")
        return

    if not space:
        await message.answer("Пространство не найдено.")
        return

    try:
        current_space = await get_user_space(user_id)
    except Exception:
        await message.answer("Не удалось проверить пространство. Попробуй ещё раз.")
        return

    if current_space:
        await message.answer(
            f"Ты уже в пространстве «{current_space['title']}». Сначала /leave."
        )
        return

    try:
        cnt = await count_members(space["id"])
    except Exception:
        await message.answer("Не удалось проверить количество участников.")
        return

    if cnt >= MAX_MEMBERS:
        await message.answer("Уже 5 участников.")
        return

    display_name = (
        message.from_user.first_name
        or message.from_user.username
        or str(user_id)
    )

    try:
        await add_member(space["id"], user_id, display_name)
    except Exception:
        await message.answer("Не удалось присоединиться к пространству.")
        return

    await message.answer(f"✅ Ты в пространстве «{space['title']}»!")


@spaces_router.message(Command("my"))
@spaces_router.message(F.text == "🏠 Пространство")
async def my_space_handler(message: Message) -> None:
    user_id = message.from_user.id

    try:
        space = await get_user_space(user_id)
    except Exception:
        await message.answer("Не удалось получить информацию о пространстве.")
        return

    if not space:
        await message.answer("Ты не в пространстве. /create или /join КОД")
        return

    try:
        cnt = await count_members(space["id"])
        members = await get_space_members_with_names(space["id"])
    except Exception:
        await message.answer("Не удалось получить список участников.")
        return

    member_lines = [
        f"• {member['display_name']}" for member in members
    ]
    member_list = "\n".join(member_lines)

    await message.answer(
        f"🏠 «{space['title']}»\n"
        f"🔑 <code>{space['invite_code']}</code>\n"
        f"👥 Участники ({cnt}/5):\n{member_list}",
        parse_mode="HTML",
    )


@spaces_router.message(Command("leave"))
async def leave_space_handler(message: Message) -> None:
    user_id = message.from_user.id

    try:
        space = await get_user_space(user_id)
    except Exception:
        await message.answer("Не удалось проверить пространство. Попробуй ещё раз.")
        return

    if not space:
        await message.answer("Ты не в пространстве.")
        return

    try:
        await remove_member(space["id"], user_id)
    except Exception:
        await message.answer("Не удалось выйти из пространства.")
        return

    await message.answer(f"Ты вышел из «{space['title']}».")


async def handle_start_with_args(message: Message, args: str) -> None:
    if args.startswith("join_"):
        code = args[5:]
        await join_by_code(message, code)