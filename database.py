import aiosqlite

from config import DB_PATH


async def init_db() -> None:
    """Создаёт все таблицы в базе данных, если они ещё не существуют."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Включаем поддержку внешних ключей (в SQLite она отключена по умолчанию)
        await conn.execute("PRAGMA foreign_keys = ON")

        # Таблица пользователей
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Таблица пространств (например, "Наша квартира")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                invite_code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                month_limit REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Таблица участников пространств
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                space_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                display_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(space_id, user_id),
                FOREIGN KEY(space_id) REFERENCES spaces(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            )
            """
        )

        # Таблица трат
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                space_id INTEGER NOT NULL,
                payer_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(space_id) REFERENCES spaces(id) ON DELETE CASCADE,
                FOREIGN KEY(payer_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            )
            """
        )

        # Таблица долей участников в тратах
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expense_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                share_amount REAL NOT NULL,
                FOREIGN KEY(expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            )
            """
        )

        await conn.commit()


async def add_user(telegram_id: int, username: str | None, first_name: str | None) -> None:
    """Добавляет пользователя в базу, если его там ещё нет."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (telegram_id, username, first_name),
        )
        await conn.commit()


async def get_user(telegram_id: int) -> aiosqlite.Row | None:
    """Возвращает строку пользователя по его telegram_id или None, если не найден."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        return await cursor.fetchone()


async def create_space(title: str, invite_code: str, created_by: int) -> int:
    """Создаёт новое пространство и возвращает его id."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        cursor = await conn.execute(
            "INSERT INTO spaces (title, invite_code, created_by) VALUES (?, ?, ?)",
            (title, invite_code, created_by),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_space_by_code(invite_code: str) -> aiosqlite.Row | None:
    """Возвращает строку пространства по инвайт-коду или None, если не найдено."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM spaces WHERE invite_code = ?",
            (invite_code,),
        )
        return await cursor.fetchone()


async def get_space_by_id(space_id: int) -> aiosqlite.Row | None:
    """Возвращает строку пространства по id или None, если не найдено."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM spaces WHERE id = ?",
            (space_id,),
        )
        return await cursor.fetchone()


async def add_member(space_id: int, user_id: int, display_name: str | None) -> None:
    """Добавляет участника в пространство, если он ещё не состоит в нём."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(
            "INSERT OR IGNORE INTO members (space_id, user_id, display_name) VALUES (?, ?, ?)",
            (space_id, user_id, display_name),
        )
        await conn.commit()


async def get_members(space_id: int) -> list[aiosqlite.Row]:
    """Возвращает список участников пространства."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM members WHERE space_id = ?",
            (space_id,),
        )
        return await cursor.fetchall()


async def is_member(space_id: int, user_id: int) -> bool:
    """Проверяет, состоит ли пользователь в пространстве."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM members WHERE space_id = ? AND user_id = ?",
            (space_id, user_id),
        )
        row = await cursor.fetchone()
        return row is not None


async def get_user_spaces(user_id: int) -> list[aiosqlite.Row]:
    """Возвращает список пространств, в которых состоит пользователь."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT spaces.*
            FROM spaces
            JOIN members ON members.space_id = spaces.id
            WHERE members.user_id = ?
            """,
            (user_id,),
        )
        return await cursor.fetchall()


async def get_user_space(user_id: int) -> aiosqlite.Row | None:
    """Возвращает одно пространство пользователя или None, если пользователь ни в одном не состоит."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT spaces.*
            FROM spaces
            JOIN members ON members.space_id = spaces.id
            WHERE members.user_id = ?
            LIMIT 1
            """,
            (user_id,),
        )
        return await cursor.fetchone()


async def count_members(space_id: int) -> int:
    """Возвращает количество участников пространства."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM members WHERE space_id = ?",
            (space_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def remove_member(space_id: int, user_id: int) -> None:
    """Удаляет пользователя из пространства."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM members WHERE space_id = ? AND user_id = ?",
            (space_id, user_id),
        )
        await conn.commit()


async def get_space_members_with_names(space_id: int) -> list[aiosqlite.Row]:
    """Возвращает участников пространства с отображаемыми именами из members/users."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT
                members.id,
                members.space_id,
                members.user_id,
                COALESCE(
                    members.display_name,
                    users.first_name,
                    users.username,
                    CAST(users.telegram_id AS TEXT)
                ) AS display_name,
                members.joined_at,
                users.username,
                users.first_name
            FROM members
            JOIN users ON users.telegram_id = members.user_id
            WHERE members.space_id = ?
            ORDER BY members.joined_at, members.id
            """,
            (space_id,),
        )
        return await cursor.fetchall()


async def code_exists(invite_code: str) -> bool:
    """Проверяет, существует ли пространство с указанным инвайт-кодом."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM spaces WHERE invite_code = ? LIMIT 1",
            (invite_code,),
        )
        row = await cursor.fetchone()
        return row is not None


async def add_expense(
    space_id: int,
    payer_id: int,
    amount: float,
    category: str,
    description: str | None,
    member_ids: list[int],
) -> int:
    """Добавляет трату и поровну распределяет её между указанными участниками."""
    if not member_ids:
        raise ValueError("Список участников для распределения траты не может быть пустым.")

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")

        # Добавляем основную запись о трате.
        cursor = await conn.execute(
            """
            INSERT INTO expenses (
                space_id,
                payer_id,
                amount,
                category,
                description
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (space_id, payer_id, amount, category, description),
        )

        expense_id = cursor.lastrowid

        # Рассчитываем равную долю для каждого участника.
        share = amount / len(member_ids)

        # Создаём доли всех участников в рамках одной транзакции.
        for member_id in member_ids:
            await conn.execute(
                """
                INSERT INTO expense_shares (
                    expense_id,
                    user_id,
                    share_amount
                )
                VALUES (?, ?, ?)
                """,
                (expense_id, member_id, share),
            )

        await conn.commit()
        return expense_id


async def get_balance(
    space_id: int,
) -> list[tuple[int, str, int, str, float]]:
    """Возвращает список долгов между участниками пространства."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Получаем всех участников и их отображаемые имена.
        cursor = await conn.execute(
            """
            SELECT
                members.user_id,
                COALESCE(
                    members.display_name,
                    users.first_name,
                    users.username,
                    CAST(users.telegram_id AS TEXT)
                ) AS display_name
            FROM members
            JOIN users ON users.telegram_id = members.user_id
            WHERE members.space_id = ?
            """,
            (space_id,),
        )
        members = await cursor.fetchall()

        # Получаем общую сумму, которую заплатил каждый участник.
        cursor = await conn.execute(
            """
            SELECT
                payer_id AS user_id,
                SUM(amount) AS paid_total
            FROM expenses
            WHERE space_id = ?
            GROUP BY payer_id
            """,
            (space_id,),
        )
        paid_rows = await cursor.fetchall()

        # Получаем общую сумму долей каждого участника.
        cursor = await conn.execute(
            """
            SELECT
                expense_shares.user_id,
                SUM(expense_shares.share_amount) AS owed_total
            FROM expense_shares
            JOIN expenses
                ON expenses.id = expense_shares.expense_id
            WHERE expenses.space_id = ?
            GROUP BY expense_shares.user_id
            """,
            (space_id,),
        )
        owed_rows = await cursor.fetchall()

        # Собираем суммы в словари для удобного расчёта баланса.
        paid_totals = {
            int(row["user_id"]): float(row["paid_total"] or 0)
            for row in paid_rows
        }
        owed_totals = {
            int(row["user_id"]): float(row["owed_total"] or 0)
            for row in owed_rows
        }

        # Формируем итоговый баланс каждого участника.
        balances: list[tuple[int, str, float]] = []
        for member in members:
            user_id = int(member["user_id"])
            display_name = member["display_name"]
            if display_name is None:
                display_name = str(user_id)

            paid_total = paid_totals.get(user_id, 0.0)
            owed_total = owed_totals.get(user_id, 0.0)
            balance = paid_total - owed_total

            balances.append(
                (
                    user_id,
                    str(display_name),
                    balance,
                )
            )

        # Должники: чем больше сумма долга, тем раньше участник в списке.
        debtors = [
            (user_id, name, -balance)
            for user_id, name, balance in balances
            if balance < -1e-9
        ]
        debtors.sort(key=lambda item: item[2], reverse=True)

        # Кредиторы: чем больше должны участнику, тем раньше он в списке.
        creditors = [
            (user_id, name, balance)
            for user_id, name, balance in balances
            if balance > 1e-9
        ]
        creditors.sort(key=lambda item: item[2], reverse=True)

        # Жадно сопоставляем крупнейших должников и кредиторов.
        result: list[tuple[int, str, int, str, float]] = []

        debtor_index = 0
        creditor_index = 0

        while debtor_index < len(debtors) and creditor_index < len(creditors):
            debtor_id, debtor_name, debt_amount = debtors[debtor_index]
            creditor_id, creditor_name, credit_amount = creditors[creditor_index]

            transfer = min(debt_amount, credit_amount)

            if transfer > 1e-9:
                result.append(
                    (
                        debtor_id,
                        debtor_name,
                        creditor_id,
                        creditor_name,
                        round(transfer, 2),
                    )
                )

            # Уменьшаем остатки после перевода.
            debtors[debtor_index] = (
                debtor_id,
                debtor_name,
                debt_amount - transfer,
            )
            creditors[creditor_index] = (
                creditor_id,
                creditor_name,
                credit_amount - transfer,
            )

            # Переходим к следующему участнику, когда текущий расчёт погашен.
            if debtors[debtor_index][2] <= 1e-9:
                debtor_index += 1

            if creditors[creditor_index][2] <= 1e-9:
                creditor_index += 1

        return result


async def get_history(space_id: int, limit: int = 10) -> list[aiosqlite.Row]:
    """Возвращает последние N трат с именем плательщика."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT
                expenses.*,
                COALESCE(
                    users.first_name,
                    users.username,
                    CAST(users.telegram_id AS TEXT)
                ) AS payer_name
            FROM expenses
            JOIN users ON users.telegram_id = expenses.payer_id
            WHERE expenses.space_id = ?
            ORDER BY expenses.created_at DESC, expenses.id DESC
            LIMIT ?
            """,
            (space_id, limit),
        )
        return await cursor.fetchall()


async def get_expenses_by_category(space_id: int) -> dict[str, float]:
    """Возвращает общую сумму трат по каждой категории за всё время."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            """
            SELECT
                category,
                SUM(amount) AS total_amount
            FROM expenses
            WHERE space_id = ?
            GROUP BY category
            ORDER BY category
            """,
            (space_id,),
        )
        rows = await cursor.fetchall()

        return {
            row[0]: round(float(row[1] or 0), 2)
            for row in rows
        }


async def get_expenses_by_member(space_id: int) -> dict[str, float]:
    """Возвращает общую сумму, которую заплатил каждый участник."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            """
            SELECT
                COALESCE(
                    members.display_name,
                    users.first_name,
                    users.username,
                    CAST(users.telegram_id AS TEXT)
                ) AS display_name,
                SUM(expenses.amount) AS total_paid
            FROM expenses
            JOIN users
                ON users.telegram_id = expenses.payer_id
            LEFT JOIN members
                ON members.user_id = expenses.payer_id
                AND members.space_id = expenses.space_id
            WHERE expenses.space_id = ?
            GROUP BY expenses.payer_id, display_name
            ORDER BY display_name
            """,
            (space_id,),
        )
        rows = await cursor.fetchall()

        return {
            str(row[0]): round(float(row[1] or 0), 2)
            for row in rows
        }
