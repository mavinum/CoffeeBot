"""
################################################################################

Helpers to compute consumption statistics from the user DB.

This module provides a small `StatsRepo` class that runs efficient SQL
aggregations against the `user_stats` table to return per-category totals
for requested time ranges (total, month, week).
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

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger

from coffeebot.db.users import UserDB


@dataclass(frozen=True)
class CategoryCount:
    """Aggregate counts for one category across time windows."""

    category: str
    total: int = 0
    month: int = 0
    week: int = 0


@dataclass(frozen=True)
class ConsumptionSummary:
    """Typed summary of purchase counts with per-category and overall totals."""

    by_category: dict[str, CategoryCount]
    total: int = 0
    month: int = 0
    week: int = 0


class StatsRepo:
    """
    Provide aggregated consumption statistics.

    The class requires an already-connected `UserDB` instance (or at least
    one where `connect()` was called). It uses lightweight SQL `SUM()`
    aggregations grouped by `category`.
    """

    def __init__(self, user_db: UserDB):
        self._db = user_db

    def _format_ts(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _query_numbers(
        self, start: datetime | None = None, end: datetime | None = None, category: str | None = None
    ) -> dict[str, int]:
        """
        Return a category -> count mapping for the given time window.

        If `category` is provided, only that category is queried. If `start` is
        None, all available rows are counted without a timestamp filter.
        """
        if not self._db.is_connected():
            logger.error("DB not connected - cannot query stats")
            return {}

        _, cur = self._db.require_connection()
        params: list[str | datetime] = []
        query = "SELECT category, COUNT(*) FROM user_stats"

        if category is not None:
            query += " WHERE category = ?"
            params.append(category)

        if start is not None:
            start_ts = self._format_ts(start)
            end_ts = self._format_ts(end or datetime.now())
            if category is not None:
                query += " AND timestamp >= ? AND timestamp <= ?"
            else:
                query += " WHERE timestamp >= ? AND timestamp <= ?"
            params.extend([start_ts, end_ts])

        query += " GROUP BY category"
        cur.execute(query, params)
        rows = cur.fetchall()

        result: dict[str, int] = {}
        for cat, val in rows:
            try:
                result[str(cat)] = int(val) if val is not None else 0
            except (TypeError, ValueError):
                result[str(cat)] = 0
        return result

    async def get_consumption_stats_async(self) -> ConsumptionSummary:
        """Run the database aggregation in a worker thread without blocking the UI."""
        if not self._db.is_connected():
            return await asyncio.to_thread(self.get_consumption_stats)
        return await asyncio.to_thread(self._get_consumption_stats_in_worker)

    def _get_consumption_stats_in_worker(self) -> ConsumptionSummary:
        with UserDB(self._db.database_path) as user_db:
            return StatsRepo(user_db).get_consumption_stats()

    def get_consumption_stats(self) -> ConsumptionSummary:
        """Return a typed, per-category summary for total, month and week conversions."""
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

        total_by_cat = self._query_numbers()
        month_by_cat = self._query_numbers(month_start, now)
        week_by_cat = self._query_numbers(week_start, now)

        categories = set(total_by_cat) | set(month_by_cat) | set(week_by_cat)
        by_category: dict[str, CategoryCount] = {}

        for category in sorted(categories):
            by_category[category] = CategoryCount(
                category=category,
                total=int(total_by_cat.get(category, 0)),
                month=int(month_by_cat.get(category, 0)),
                week=int(week_by_cat.get(category, 0)),
            )

        return ConsumptionSummary(
            by_category=by_category,
            total=sum(item.total for item in by_category.values()),
            month=sum(item.month for item in by_category.values()),
            week=sum(item.week for item in by_category.values()),
        )
