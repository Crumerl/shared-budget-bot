"""
Скрипт ежедневного коммита.
Дописывает запись в DEVLOG.md, коммитит и пушит на GitHub.
Запускается через Планировщик задач Windows.
"""

import os
import subprocess
from datetime import date

# ---- настройки ----
REPO_PATH = r"D:\VSCode\shared-budget-bot"
DEVLOG = os.path.join(REPO_PATH, "DEVLOG.md")
START_DATE = date(2026, 9, 22)  # день первого коммита

# Темы, которые ротируются по дням
TOPICS = [
    "Ревизия обработчиков aiogram",
    "Проверка логики расчёта долгов",
    "Улучшение обработки ошибок в database.py",
    "Обновление README и документации",
    "Проверка граничных случаев в add_expense",
    "Рефакторинг хендлеров пространств",
    "Тестирование FSM выбора участников",
    "Проверка работы deep-link /start join_",
    "Анализ покрытия функций БД",
    "Улучшение формата вывода баланса",
    "Правки в форматировании сумм",
    "Ревизия инвайт-кодов и их уникальности",
    "Проверка лимита в 5 участников",
    "Улучшение текстов сообщений бота",
    "Разбор логирования и отладочных сообщений",
    "Проверка поведения бота при выходе /leave",
    "Ревизия работы с прокси AiohttpSession",
    "Проверка корректности клавиатур",
    "Ревизия структуры проекта",
    "Анализ архитектуры модулей",
]


def get_day_number() -> int:
    """Сколько дней прошло с момента старта."""
    return (date.today() - START_DATE).days + 1


def main() -> None:
    os.chdir(REPO_PATH)

    day = get_day_number()
    today = date.today().strftime("%d.%m.%Y")
    topic = TOPICS[(day - 1) % len(TOPICS)]

    # Дописываем запись в журнал
    with open(DEVLOG, "a", encoding="utf-8") as f:
        f.write(f"\n### День {day} — {today}\n")
        f.write(f"- {topic}\n")

    # Git-команды
    subprocess.run(["git", "add", "DEVLOG.md"], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"devlog: день {day} — {topic}"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)

    print(f"Коммит за день {day} отправлен.")


if __name__ == "__main__":
    main()