"""
Скрипт ежедневного коммита.
Дописывает запись в devlog.md, коммитит и пушит на GitHub.
Запускается через Планировщик задач Windows.
"""

import os
import subprocess
import sys
from datetime import date

# ---- настройки ----
REPO_PATH = r"D:\VSCode\shared-budget-bot"
DEVLOG_NAME = "devlog.md"
DEVLOG = os.path.join(REPO_PATH, DEVLOG_NAME)
START_DATE = date(2026, 9, 22)

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


def run_git(args: list[str]) -> None:
    """Запускает git-команду и печатает её вывод."""
    print(f">>> git {' '.join(args)}")
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_PATH,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.stdout:
        print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        print(f"!!! git {' '.join(args)} завершился с кодом {result.returncode}")
        sys.exit(result.returncode)


def main() -> None:
    day = (date.today() - START_DATE).days + 1
    today = date.today().strftime("%d.%m.%Y")
    topic = TOPICS[(day - 1) % len(TOPICS)]

    # Дописываем запись в журнал
    with open(DEVLOG, "a", encoding="utf-8") as f:
        f.write(f"\n### День {day} — {today}\n")
        f.write(f"- {topic}\n")

    # Git-команды
    run_git(["add", DEVLOG_NAME])
    run_git(["commit", "-m", f"devlog: день {day} — {topic}"])
    run_git(["push"])

    print(f"\nКоммит за день {day} отправлен.")


if __name__ == "__main__":
    main()