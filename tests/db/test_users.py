# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only

from decimal import ROUND_HALF_UP, Decimal
from io import StringIO
from pathlib import Path

import pytest
from loguru import logger

from coffeebot.db.users import CreateUser, UserDB


@pytest.mark.parametrize(
    "add_data",
    [
        CreateUser("First", "Testname", "group", "mail@mail.com", "1", 0.00),
        CreateUser("Second", "Name", "Secondgroup 1", "Second@Name.de", "12345", 12.8),
        CreateUser("Third", "Surname", "group_2", "name@email.com", "23465", -130.14),
        CreateUser("Fourth", "Last Name", "group, the third", "some@mymail.de", "456", 285.00),
    ],
)
def test_add_and_get_user(add_data: CreateUser, tmp_path: Path) -> None:
    """Test adding and getting user data from DB."""
    db_path = tmp_path / "users.db"
    with UserDB(db_path) as users:
        users.add(add_data)
        # Assuming users are added with ID 1 in a fresh DB
        entry = users.get_user(1)

    assert entry.forename == add_data.forename
    assert entry.surename == add_data.surename


@pytest.mark.parametrize("price", [2.5, 3.1, 0.3, -1.4, 100.40, -270.0])
def test_bill_user(price: float, tmp_path: Path) -> None:
    """Test billing to change the users balance."""
    db_path = tmp_path / "bill.db"
    with UserDB(db_path) as users:
        users.add(CreateUser("First", "Last", "Group", "test@example.com", None, 10.0))
        usr = users.get_user(1)
        users.bill(1, "cat_1", price)
        usr_after = users.get_user(1)

    expected_balance = (Decimal(str(usr.balance)) - Decimal(str(price))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert Decimal(str(usr_after.balance)) == expected_balance


def test_bill_statistics_do_not_store_user_id(tmp_path: Path) -> None:
    """Verify billing writes a persistent statistics row without a user link."""
    database_path = tmp_path / "stats.db"
    with UserDB(database_path) as users:
        users.add(CreateUser("First", "Last", "Group", "test@example.com", "12345", 10.0))
        users.bill(1, "coffee", 1.25)
        _, cursor = users.require_connection()
        cursor.execute("PRAGMA table_info(user_stats)")
        columns = {row[1] for row in cursor.fetchall()}

    with UserDB(database_path) as users:
        _, cursor = users.require_connection()
        cursor.execute("SELECT timestamp, category, price FROM user_stats")
        rows = cursor.fetchall()

    assert "user_id" not in columns
    assert len(rows) == 1
    assert rows[0][1:] == ("coffee", 1.25)


def test_balance_operations_quantize_to_cents(tmp_path: Path) -> None:
    """Round half-cent prices and deposits before storing balances."""
    with UserDB(tmp_path / "rounded-balances.db") as users:
        users.add(CreateUser("First", "Last", "Group", "test@example.com", None, 10.0))

        users.bill(1, "coffee", 0.105)
        billed_user = users.get_user(1)
        users.transfer(1, 0.105)
        transferred_user = users.get_user(1)

    assert Decimal(str(billed_user.balance)) == Decimal("9.90")
    assert Decimal(str(transferred_user.balance)) == Decimal("10.01")


@pytest.mark.parametrize(
    ("user_data", "user_id"),
    [
        ({"forename": "Updated", "surename": "User"}, 1),
        ({"forename": "Alternative", "surename": "Other Name", "telegram_id": 100}, 2),
        ({"workgroup": "New", "surename": "& Dynamic", "email": "something@new.de"}, 3),
        ({"telegram_id": 42, "email": "completely@new.de"}, 4),
    ],
)
def test_update_user(user_data: dict, user_id: int, tmp_path: Path) -> None:
    """Test updating user data in DB."""
    db_path = tmp_path / "update.db"
    with UserDB(db_path) as users:
        # Seed users for the update test
        for i in range(1, 5):
            users.add(CreateUser(f"User{i}", f"Last{i}", "Group", f"user{i}@test.com", None, 10.0))

        user_before = users.get_user(user_id)
        users.update(user_data, user_id)
        user_after = users.get_user(user_id)
        user_before.update(user_data)
    assert user_before == user_after


def test_delete_user(tmp_path: Path) -> None:
    """Test deleting user from DB."""
    db_path = tmp_path / "delete.db"
    with UserDB(db_path) as users:
        users.add(CreateUser("First", "Last", "Group", "test@example.com", None, 10.0))
        users.delete(1)

        assert users.get_user(1) is None


def test_delete_user_removes_bookkeeping_and_keeps_anonymized_stats(tmp_path: Path) -> None:
    """Delete user-linked records but retain unlinked consumption statistics."""
    database_path = tmp_path / "delete-user.db"
    with UserDB(database_path) as users:
        users.add(CreateUser("First", "User", "Group", "first@example.com", None, 10.0))
        users.add(CreateUser("Second", "User", "Group", "second@example.com", None, 20.0))
        conn, cursor = users.require_connection()
        cursor.executemany(
            "INSERT INTO bookkeeping (timestamp, balance_old, balance_new, deposit, user_id) VALUES (?, ?, ?, ?, ?)",
            [("2026-10-09 10:00:00", "10.0", 15.0, 5.0, 1), ("2026-10-09 11:00:00", "20.0", 25.0, 5.0, 2)],
        )
        cursor.execute(
            "INSERT INTO user_stats (timestamp, category, price) VALUES (?, ?, ?)",
            ("2026-10-09 10:00:00", "coffee", 1.25),
        )
        conn.commit()

        users.delete(1)

        cursor.execute("SELECT user_id FROM bookkeeping ORDER BY user_id")
        remaining_bookkeeping = cursor.fetchall()
        cursor.execute("SELECT timestamp, category, price FROM user_stats")
        remaining_stats = cursor.fetchall()
        deleted_user = users.get_user(1)

    assert deleted_user is None
    assert remaining_bookkeeping == [(2,)]
    assert remaining_stats == [("2026-10-09 10:00:00", "coffee", 1.25)]


def test_personal_data_is_not_written_to_logs(tmp_path: Path) -> None:
    """Ensure user profile and transaction details are excluded from log output."""
    log_output = StringIO()
    sink_id = logger.add(log_output, format="{message}")
    database_path = tmp_path / "private-data.db"
    user = CreateUser("PrivateFirst", "PrivateLast", "PrivateGroup", "private@example.com", "987654321", 21.37)

    try:
        with UserDB(database_path) as users:
            users.add(user)
            users.update({"email": "updated@example.com"}, 1)
            users.bill(1, "private-category", 3.19)
            users.delete(1)
    finally:
        logger.remove(sink_id)

    output = log_output.getvalue()
    for private_value in (
        "PrivateFirst",
        "PrivateLast",
        "PrivateGroup",
        "private@example.com",
        "updated@example.com",
        "987654321",
        "21.37",
        "private-category",
        "3.19",
        str(database_path),
    ):
        assert private_value not in output
