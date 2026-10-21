"""
################################################################################

DB module to access user data and stats saved in a sqlite DB.

################################################################################
Copyright (C) 2026 Mavinum
SPDX-License-Identifier: GPL-3.0-only
See LICENSE in the project root.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 only.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See LICENSE
for more details.
################################################################################
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from coffeebot.db.migration import CURRENT_VERSION, apply_migrations, init_meta_table, set_schema_version

if TYPE_CHECKING:
    import types

# Table names
USERS = "users"
STATS = "user_stats"
BOOKKEEPING = "bookkeeping"
CENT = Decimal("0.01")

BASE_DIR = Path(__file__).parent


class Rating(StrEnum):
    """Enum representation of balance rating emojis."""

    ZERO = "\U0001f636"  # 😶
    ONE = "\U0001f47f"  # 👿
    TWO = "\U0001f92c"  # 🤬
    THREE = "\U0001f621"  # 😡
    FOUR = "\U0001fae0"  # 🫠
    FIVE = "\U0001f62c"  # 😬
    SIX = "\U0001f9d0"  # 🧐
    SEVEN = "\U0001f642"  # 🙂
    EIGHT = "\U0001f603"  # 😃
    NINE = "\U0001f601"  # 😁
    TEN = "\U0001f970"  # 🥰

    @classmethod
    def get_rating(cls, balance: float) -> Rating:
        """Return rating emoji for the given balance."""
        index = min(max(int((balance + 270) // 30), 0), 10)
        return list(cls)[index]


@dataclass
class CreateUser:
    """Container object for new user data."""

    forename: str
    surename: str
    workgroup: str
    email: str
    telegram_id: str | None
    balance: float


@dataclass
class User:
    """Container object to hold all user information retrieved form DB."""

    _user_id: int
    forename: str
    surename: str
    workgroup: str
    email: str
    telegram_id: int | None
    balance: float

    @classmethod
    def get_keys(cls) -> list[str]:
        """Retrun a list of all attribute names excep user_id."""
        return list(cls.__annotations__)[1:]

    @property
    def user_id(self) -> int:
        """Getter for user_id to protect id value."""
        return self._user_id

    def attributes(self) -> list[str]:
        """Return a list of all attribute names except user_id."""
        return list(asdict(self))[1:]

    def values(self) -> list[str | int]:
        """Return as list of all attribute values but the user_id."""
        return list(asdict(self).values())[1:]

    def all_values(self) -> list[str | int]:
        """Return as list of all attribute values including the user_id."""
        return list(asdict(self).values())

    def get_dict(self) -> dict[str, str | int]:
        """Return key value pairs of all attributes."""
        data = asdict(self)
        return {k.lstrip("_"): v for k, v in data.items()}

    def update(self, data: dict) -> None:
        """Update attributes with supplied values."""
        for k, v in data.items():
            self.__setattr__(k, v)


class UserDB:
    """Store user data from database."""

    def __init__(self, path: Path):
        self._db = path
        self.check_db()

        self._connect: sqlite3.Connection | None = None
        self._cursor: sqlite3.Cursor | None = None

    def __enter__(self):
        logger.debug("Entering DB context....")
        self.connect()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, exc_tb: types.TracebackType | None
    ):
        self.close()
        if (exc_type, exc_value, exc_tb) != (None, None, None):
            logger.opt(exception=(exc_type, exc_value, exc_tb)).exception("Exception occurred - leaving DB context")
        else:
            logger.debug("Leaving DB context")

    # region Public methods

    @property
    def database_path(self) -> Path:
        """Return the path to the SQLite database."""
        return self._db

    def connect(self) -> None:
        """Connect to database and apply migrations."""
        self._connect = sqlite3.connect(self._db)
        self._cursor = self._connect.cursor()
        logger.success("DB connection established successfully")

        # Apply any pending migrations and handle initial DB setup
        apply_migrations(self._connect)

    def check_db(self) -> None:
        """Ensure database file exists and has a basic schema if fresh."""
        if self._db.is_file():
            return

        logger.info("No database file found. Creating a new database...")

        self._db.parent.mkdir(parents=True, exist_ok=True)

        try:
            with closing(sqlite3.connect(self._db)) as conn, conn:
                init_db_sql = BASE_DIR / "init_DB.sql"
                with init_db_sql.open(mode="r", encoding="utf-8") as file:
                    script = file.read()
                conn.executescript(script)

                init_meta_table(conn)
                set_schema_version(conn, CURRENT_VERSION)

                logger.success("New database initialized successfully.")
        except (OSError, sqlite3.Error) as e:
            logger.error(f"Failed to initialize fresh database: {e}")
            raise

    def get_users(self) -> list | None:
        """Load all user data from database."""
        if not self.is_connected():
            return None
        _, cursor = self.require_connection()
        cursor.execute(f"SELECT * FROM {USERS}")
        logger.debug("Loading user data from DB")
        return cursor.fetchall()

    def get_users_for_export(self) -> list[tuple] | None:
        """Load all user data for export (without telegram_id)."""
        if not self.is_connected():
            return None
        _, cursor = self.require_connection()
        cursor.execute(f"SELECT ID, forename, surename, workgroup, email, balance FROM {USERS}")
        logger.info("Loading user data for export from DB")
        return cursor.fetchall()

    def get_user(self, user_id: int) -> User | None:
        """Get data for user id."""
        if not self.is_connected():
            return None

        _, cursor = self.require_connection()
        query = f"SELECT * FROM {USERS} WHERE ID=:id"
        cursor.execute(query, {"id": user_id})
        data = cursor.fetchone()

        logger.debug("Loading single user data form DB")
        if data:
            return User(*data)
        return None

    def bill(self, user_id: int, category: str, price: float) -> float | None:
        """Substract price from balance of user with specified id."""
        if not self.is_connected():
            return None

        conn, cursor = self.require_connection()

        get_query = f"SELECT balance FROM {USERS} WHERE ID=:id"
        cursor.execute(get_query, {"id": user_id})

        balance = Decimal(str(cursor.fetchone()[0]))
        price_decimal = Decimal(str(price))
        balance = (balance - price_decimal).quantize(CENT, rounding=ROUND_HALF_UP)

        set_query = f"UPDATE {USERS} SET balance = ? WHERE ID = ?"
        cursor.execute(set_query, (float(balance), user_id))
        conn.commit()

        self._log_stats(category, price)
        logger.debug("Recorded beverage transaction")

        return float(balance)

    def add(self, user_data: CreateUser) -> None:
        """Insert user into database."""
        if not self.is_connected():
            return

        conn, cursor = self.require_connection()
        data = asdict(user_data)
        columns = ", ".join(data.keys())
        values = ", ".join(f":{key}" for key in data)
        query = f"INSERT INTO {USERS} ({columns}) VALUES ({values})"
        try:
            cursor.execute(query, data)
            conn.commit()
            logger.info("Added user record to database")

        except sqlite3.Error as e:
            logger.exception(f"{e}: Failed to create user record")
            conn.rollback()

    def update(self, user_data: dict | User, user_id: int | None = None) -> None:
        """
        Update user data in database.

            user_data: (dict | User): Dictionary of fields to update or User object
            user_id: (int | None): User ID to update. If None, it will be extracted form dict or User object
        Notes:
            - Only fields defined as attribute of User can be updated.
            - The 'balance' and 'user_id' fileds cannot be changed (-> see 'transfer()' or 'bill()').
            - If user does not exists or none of the values has changed, the DB remains unchanged.

        """
        if not self.is_connected():
            return

        conn, cursor = self.require_connection()
        if isinstance(user_data, User):
            user_id = user_data.user_id
            data = user_data.get_dict()
        else:
            user_id = user_id or user_data["user_id"]
            data = {k: v for k, v in user_data.items() if k in User.get_keys()}
            data["user_id"] = user_id

        # Check existing user data
        user = self.get_user(user_id)
        if user is None:
            logger.error("Cannot update none-existing user")
            return

        # Create list of changed parametes to update
        user = user.get_dict()
        changed = [k for k, v in data.items() if user[k] != v and k != "balance"]
        if changed == []:
            logger.info("No user record changes to save")
            return

        set_clause = ", ".join(f"{k}=:{k}" for k in changed)
        query = f"UPDATE {USERS} SET {set_clause} WHERE ID=:user_id"
        try:
            cursor.execute(query, data)
            conn.commit()
            logger.info("Updated user record")
        except sqlite3.Error:
            logger.exception("Failed to update user record")
            conn.rollback()

    def transfer(self, user_id: int, amount: float) -> None:
        """Update user balance by given amount."""
        if not self.is_connected():
            return
        conn, cursor = self.require_connection()
        cursor.execute(f"SELECT balance FROM {USERS} WHERE ID=:id", {"id": user_id})
        balance_old = Decimal(str(cursor.fetchone()[0]))
        amount_decimal = Decimal(str(amount))
        balance_new = (balance_old + amount_decimal).quantize(CENT, rounding=ROUND_HALF_UP)

        query = f"UPDATE {USERS} SET balance = ? WHERE ID = ?"
        try:
            cursor.execute(query, (float(balance_new), user_id))
            self._log_transaction(user_id, float(balance_old), float(balance_new), float(amount_decimal))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"{e}: Failed to update account balance")
            conn.rollback()

    def delete(self, user_id: int) -> None:
        """Delete user with specified id form database."""
        if not self.is_connected():
            return
        conn, cursor = self.require_connection()
        try:
            cursor.execute(f"DELETE FROM {BOOKKEEPING} WHERE user_id=?", (user_id,))
            cursor.execute(f"DELETE FROM {USERS} WHERE ID=?", (user_id,))
            conn.commit()
            logger.warning("Deleted user account")

        except sqlite3.Error as e:
            logger.error(f"{e}: Failed to delete user account")
            conn.rollback()

    def require_connection(self) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
        """Return a connected DB connection and cursor or raise if missing."""
        if self._connect is None or self._cursor is None:
            msg = "No DB connection!"
            raise RuntimeError(msg)
        return self._connect, self._cursor

    def is_connected(self) -> bool:
        """Check if the DB connection exists."""
        if self._connect is None or self._cursor is None:
            logger.error("No DB connection, cannot execute queries!")
            return False
        return True

    def close(self) -> None:
        """Close cursor and connection."""
        if self._cursor is not None and self._connect is not None:
            self._cursor.close()
            self._connect.close()
            logger.info("Closing DB connection")

    # endregion

    # region Private methods

    def _log_stats(self, category: str, price: float) -> None:
        """Log time, item and price payed."""
        conn, cursor = self.require_connection()
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(f"INSERT INTO {STATS} (timestamp, category, price) VALUES (?, ?, ?)", (time, category, price))
        conn.commit()

    def _log_transaction(self, user_id: int, balance_old: float, balance_new: float, deposit: float) -> None:
        """Log balance transactions."""
        conn, cursor = self.require_connection()
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            f"INSERT INTO {BOOKKEEPING} (timestamp, balance_old, balance_new, deposit, user_id) VALUES (?, ?, ?, ?, ?)",
            (time, balance_old, balance_new, deposit, user_id),
        )
        conn.commit()

    # endregion
