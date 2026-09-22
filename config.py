import os
from pathlib import Path

from dotenv import load_dotenv

# Определяем путь к .env файлу (лежит рядом с этим файлом, в корне проекта)
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Загружаем переменные окружения из .env
load_dotenv(dotenv_path=ENV_PATH)

# Токен бота — обязательная переменная
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в .env")

# Путь к файлу базы данных SQLite (по умолчанию — budget.db в корне проекта)
DB_PATH = os.getenv("DB_PATH", "budget.db") 