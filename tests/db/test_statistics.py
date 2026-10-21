import asyncio
from datetime import datetime
from pathlib import Path

from coffeebot.db.statistics import StatsRepo
from coffeebot.db.users import UserDB


def test_consumption_stats_aggregate_category_counts(tmp_path: Path) -> None:
    """Aggregate purchase totals by category and across all categories."""
    db_path = tmp_path / "stats.db"
    with UserDB(db_path) as users:
        conn, cursor = users.require_connection()
        cursor.execute("DELETE FROM user_stats")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.executemany(
            "INSERT INTO user_stats (timestamp, category, price) VALUES (?, ?, ?)",
            [(now, "espresso", 2.50), (now, "espresso", 3.50), (now, "latte", 1.75)],
        )
        conn.commit()

        summary = StatsRepo(users).get_consumption_stats()

    assert summary.total == 3
    assert summary.by_category["espresso"].total == 2
    assert summary.by_category["latte"].total == 1


def test_get_consumption_stats_async_uses_worker_database_connection(tmp_path: Path) -> None:
    """Retrieve statistics in a worker thread without reusing the caller's SQLite connection."""
    db_path = tmp_path / "stats_async.db"

    with UserDB(db_path) as users:
        conn, cursor = users.require_connection()
        cursor.execute("DELETE FROM user_stats")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.executemany(
            "INSERT INTO user_stats (timestamp, category, price) VALUES (?, ?, ?)",
            [(now, "espresso", 2.50), (now, "espresso", 3.50), (now, "latte", 1.75)],
        )
        conn.commit()

        stats = asyncio.run(StatsRepo(users).get_consumption_stats_async())

    assert stats.by_category["espresso"].total == 2
    assert stats.total == 3
    assert all(isinstance(value, int) for value in (stats.total, stats.month, stats.week))
