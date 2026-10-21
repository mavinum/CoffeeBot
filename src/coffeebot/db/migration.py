"""
################################################################################

DB Migration module to handle schema updates.

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

from loguru import logger

# Schema versions
# 0: Legacy (coffee_users table)
# 1: Initial structured release (users, user_stats, bookkeeping, meta)
CURRENT_VERSION = 1


def migrate_legacy_to_v1(conn: sqlite3.Connection) -> None:
    """Migrates the old coffee_users structure to the new version."""
    cursor = conn.cursor()

    # Check for legacy table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coffee_users'")
    if not cursor.fetchone():
        return

    logger.info("Legacy database detected. Migrating to V1...")

    try:
        # Update table name
        cursor.execute("ALTER TABLE coffee_users RENAME TO users")

        # Update columns
        cursor.execute("ALTER TABLE users RENAME COLUMN chair TO workgroup")

        cursor.execute("ALTER TABLE users ADD COLUMN telegram_id INTEGER")

        cursor.execute("UPDATE users SET telegram_id = CAST(telegram_username AS INTEGER)")

        # Remove the old column
        try:
            cursor.execute("ALTER TABLE users DROP COLUMN telegram_username")
        except sqlite3.OperationalError:
            logger.warning("Could not drop column 'telegram_username'. Your SQLite version might be too old.")

        # Create missing tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                process_id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookkeeping (
                transaction_id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                balance_old TEXT,
                balance_new REAL NOT NULL,
                deposit REAL NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        conn.commit()
        logger.info("Migration to V1 successful.")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise


def init_meta_table(conn: sqlite3.Connection) -> None:
    """Initialize the version tracking table."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Retrieve the current schema version from the meta table."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM meta WHERE key='schema_version'")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the schema version in the meta table."""
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)", (str(version),))
    conn.commit()


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Entry point to apply all pending migrations."""
    init_meta_table(conn)

    schema_version = get_schema_version(conn)
    logger.debug(f"Current DB schema version: {schema_version}")

    if schema_version < CURRENT_VERSION:
        # Version 0 (Legacy) -> 1
        migrate_legacy_to_v1(conn)
        set_schema_version(conn, CURRENT_VERSION)

    logger.debug(f"DB schema is up to date (Version {CURRENT_VERSION})")
