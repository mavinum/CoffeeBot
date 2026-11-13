# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only

import json
from pathlib import Path

from coffeebot.system.migration import main


def test_migration_copies_and_renames_files(tmp_path: Path, monkeypatch) -> None:
    """Import config and database to their configured CoffeeBot locations."""

    class TemporaryPlatformDirs:
        def __init__(self, _app_name: str, _vendor: str) -> None:
            self.user_config_path = tmp_path / "user-config"
            self.user_data_path = tmp_path / "platform-data"
            self.user_log_path = tmp_path / "logs"

    monkeypatch.setattr("coffeebot.config.settings.PlatformDirs", TemporaryPlatformDirs)
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.4.0")

    legacy_data_dir = tmp_path / "legacy-data"
    legacy_data_dir.mkdir()
    source_db = tmp_path / "old-database.sqlite"
    source_db.write_bytes(b"new database contents")
    source_config = tmp_path / "old-settings.json"
    source_config.write_text(
        json.dumps({"data_dir": str(legacy_data_dir), "db_file": "user_data.db"}), encoding="utf-8"
    )

    expected_config = tmp_path / "user-config" / "config.json"
    expected_db = legacy_data_dir / "user_data.db"
    expected_db.write_bytes(b"existing database contents")

    assert main(["--config", str(source_config), "--db", str(source_db)]) == 0

    assert expected_config.read_bytes() == source_config.read_bytes()
    assert expected_db.read_bytes() == b"new database contents"
