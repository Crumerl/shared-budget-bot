"""
Скрипт ежедневного коммита.
- Дописывает запись в devlog.md (с защитой от дублей за сегодня).
- Умно обрабатывает "нечего коммитить".
- Ждёт появления интернета перед git push.
- Повторяет git-команды при реальных ошибках.
- Пишет подробный лог в daily_commit.log.
"""

import os
import socket
import subprocess
import sys
import time
from datetime import date, datetime

# ---- настройки ----
REPO_PATH = r"D:\VSCode\shared-budget-bot"
DEVLOG_NAME = "devlog.md"
DEVLOG = os.path.join(REPO_PATH, DEVLOG_NAME)
LOG_FILE = os.path.join(REPO_PATH, "daily_commit.log")
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


def log(message: str) -> None:
    """Пишет сообщение в лог-файл и в stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_internet_available(host: str = "github.com", port: int = 443, timeout: int = 5) -> bool:
    """Проверяет, доступен ли GitHub."""
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def wait_for_internet(max_wait: int = 180) -> bool:
    """Ждёт появления соединения с GitHub. Максимум max_wait секунд."""
    log("Проверка соединения с github.com...")
    waited = 0
    while waited < max_wait:
        if is_internet_available():
            log(f"Соединение с github.com появилось (ждали {waited} сек).")
            return True
        log(f"Соединения нет. Ждём 10 сек... ({waited}/{max_wait})")
        time.sleep(10)
        waited += 10
    log("Интернет так и не появился за отведённое время.")
    return False


def run_git_once(args: list[str]) -> tuple[int, str, str]:
    """Запускает git один раз. Возвращает (код, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except Exception as e:
        return 1, "", f"Исключение: {e}"


def git_push_with_retries(retries: int = 6) -> bool:
    """Делает git push с повторами. Перед каждой попыткой ждёт интернет."""
    for attempt in range(1, retries + 1):
        if not wait_for_internet(max_wait=60):
            log(f"  Попытка {attempt}: нет соединения с github.com.")
            if attempt < retries:
                time.sleep(30)
            continue

        log(f">>> git push (попытка {attempt}/{retries})")
        code, out, err = run_git_once(["push"])
        if out.strip():
            log(f"  STDOUT: {out.strip()}")
        if err.strip():
            log(f"  STDERR: {err.strip()}")
        log(f"  Exit code: {code}")

        if code == 0:
            return True

        if attempt < retries:
            log("  Ошибка. Ждём 30 сек перед следующей попыткой.")
            time.sleep(30)

    return False


def main() -> None:
    log("=" * 60)
    log("Запуск daily_commit.py")

    day = (date.today() - START_DATE).days + 1
    today = date.today().strftime("%d.%m.%Y")
    topic = TOPICS[(day - 1) % len(TOPICS)]
    header = f"### День {day} — {today}"

    # 1. Читаем devlog
    try:
        with open(DEVLOG, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""

    need_new_entry = header not in content

    # 2. Дописываем запись, если её нет
    if need_new_entry:
        with open(DEVLOG, "a", encoding="utf-8") as f:
            f.write(f"\n{header}\n")
            f.write(f"- {topic}\n")
        log(f"Добавлена запись: {header}")
    else:
        log(f"Запись «{header}» уже существует.")

    # 3. git add devlog.md
    code, out, err = run_git_once(["add", DEVLOG_NAME])
    if code != 0:
        log(f"ОШИБКА на git add: {err}")
        sys.exit(1)

    # 4. git commit
    #    Проверяем отдельно: если "nothing to commit" — это не ошибка.
    code, out, err = run_git_once(["commit", "-m", f"devlog: день {day} — {topic}"])
    commit_output = (out + err).lower()

    if code == 0:
        log(f"Коммит создан: devlog: день {day} — {topic}")
    elif "nothing to commit" in commit_output or "no changes added" in commit_output:
        log("Коммитить нечего — devlog уже закоммичен ранее.")
    else:
        log(f"ОШИБКА на git commit (код {code}):")
        if out.strip():
            log(f"  STDOUT: {out.strip()}")
        if err.strip():
            log(f"  STDERR: {err.strip()}")
        # Не выходим — возможно, коммит есть, но локально не отправлен.
        # Попробуем push.

    # 5. git push с повторами
    if not git_push_with_retries():
        log("ОШИБКА: не удалось выполнить git push.")
        sys.exit(1)

    log(f"Коммит за день {day} успешно отправлен.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ: {e}")
        sys.exit(1)