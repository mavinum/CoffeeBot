"""
################################################################################

User data migration.

This module provides an additional entry-point for a terminal based command
to migrate data (database and settings) that have been generated with another
version or on another machine.

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

import argparse
import shutil
from collections.abc import Sequence
from pathlib import Path

from loguru import logger

from coffeebot.config.settings import Settings


def _copy_file(source: Path, destination: Path) -> None:
    """Copy a source file to its application-managed destination."""
    if not source.is_file():
        msg = f"Source file does not exist or is not a file: {source}"
        raise FileNotFoundError(msg)

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def migrate_data(db_path: Path | None = None, config_path: Path | None = None) -> tuple[Path | None, Path | None]:
    """Copy legacy database and/or settings into the locations used by CoffeeBot."""
    if db_path is None and config_path is None:
        msg = "At least one of db_path or config_path must be provided."
        raise ValueError(msg)

    settings = Settings.configure_app("Coffeebot", "Mavinum")
    config_destination = settings.path

    if config_path is not None:
        _copy_file(config_path, config_destination)
        settings.load()

    db_destination = None
    if db_path is not None:
        data_dir = settings.get("data_dir")
        db_filename = settings.get("db_file")
        if not isinstance(data_dir, str) or not isinstance(db_filename, str):
            msg = "The configured data_dir and db_file settings must be strings."
            raise ValueError(msg)
        db_destination = Path(data_dir) / db_filename
        _copy_file(db_path, db_destination)

    return db_destination, config_destination if config_path is not None else None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line data migration."""
    parser = argparse.ArgumentParser(description="Migrate CoffeeBot database and settings files.")
    parser.add_argument("--db", type=Path, help="Path to the database file to import.")
    parser.add_argument("--config", type=Path, help="Path to the settings file to import.")
    args = parser.parse_args(argv)

    if args.db is None and args.config is None:
        parser.error("provide at least one of --db or --config")

    try:
        db_destination, config_destination = migrate_data(args.db, args.config)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    if db_destination is not None:
        logger.info(f"Database copied to {db_destination}")
    if config_destination is not None:
        logger.info(f"Settings copied to {config_destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
