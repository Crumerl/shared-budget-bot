# main.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession

import config
import database

from handlers.spaces import spaces_router, handle_start_with_args
from handlers.expenses import expenses_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    command: CommandObject,
) -> None:
    """Обработчик команды /start."""

    # Deep-link /start join_ABC123
    if command.args and command.args.startswith("join_"):
        await handle_start_with_args(message, command.args)
        return

    try:
        await database.add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    except Exception as e:
        logger.exception("Не удалось сохранить пользователя: %s", e)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Добавить трату")],
            [KeyboardButton(text="📊 Баланс")],
            [KeyboardButton(text="📜 История")],
            [KeyboardButton(text="🏠 Пространство")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Это бот для общего учёта расходов.\n\n"
        "Выбери действие в меню ниже.",
        reply_markup=keyboard,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    await message.answer(
        "/start — меню\n"
        "/add СУММА КАТЕГОРИЯ — добавить трату\n"
        "/balance — кто кому должен\n"
        "/history — последние траты\n"
        "/chart — график\n"
        "/create — создать пространство\n"
        "/join КОД — присоединиться\n"
        "/my — моё пространство\n"
        "/leave — выйти"
    )


@router.message(F.text == "💰 Добавить трату")
async def add_expense_button(message: Message) -> None:
    """Показывает формат команды для добавления траты."""
    await message.answer(
        "Напиши в формате: /add СУММА КАТЕГОРИЯ\n"
        "Пример: /add 500 продукты"
    )


@router.message(F.text == "❓ Помощь")
async def help_button(message: Message) -> None:
    """Обработчик кнопки «Помощь»."""
    await cmd_help(message)


async def main() -> None:
    """Точка входа: инициализация БД и запуск polling."""
    await database.init_db()
    logger.info("База данных инициализирована")

    proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

    if proxy:
        logger.info("Используется HTTPS-прокси")
        session = AiohttpSession(proxy=proxy)
        bot = Bot(token=config.BOT_TOKEN, session=session)
    else:
        bot = Bot(token=config.BOT_TOKEN)

    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(spaces_router)
    dp.include_router(expenses_router)

    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")