"""
Settings management and organization.

App wide settings store that behaves like a dict and is backed by JSON
files. The first call to configure_app creates a shared instance that the rest
of the application can reuse.
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

import contextlib
import json
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

from filelock import FileLock, Timeout
from platformdirs import PlatformDirs

if TYPE_CHECKING:
    from collections.abc import ItemsView, Iterable, Iterator


type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list["JSONPrimitive"] | dict[str, "JSONPrimitive"]


class Settings:
    """Platform-independent storage for app and user settings."""

    _instance: Settings | None = None
    app_name = ""
    vendor = ""
    version = ""

    @classmethod
    def get_instance(cls) -> Settings:
        """Return the shared application settings instance."""
        if cls._instance is None:
            msg = "Settings have not been configured yet. Call configure_app() first."
            raise RuntimeError(msg)
        return cls._instance

    @classmethod
    def configure_app(  # noqa: PLR0913
        cls,
        app_name: str,
        vendor: str,
        *,
        config_dir: str | Path | None = None,
        default_path: str | Path | None = None,
        config_filename: str = "config.json",
        lock_timeout: int = 5,
    ) -> Settings:
        """Configure a shared settings instance for the application."""
        cls.app_name = app_name
        cls.vendor = vendor
        cls.version = metadata.version(app_name)
        cls.dirs = PlatformDirs(app_name, vendor)

        resolved_config_dir = Path(config_dir) if config_dir is not None else Path(cls.dirs.user_config_path)
        resolved_config_dir.mkdir(parents=True, exist_ok=True)

        resolved_default_path = (
            Path(default_path) if default_path is not None else Path(__file__).with_name("default.json")
        )

        if cls._instance is None:
            cls._instance = cls(resolved_config_dir / config_filename, resolved_default_path, lock_timeout=lock_timeout)
        else:
            cls._instance.path = resolved_config_dir / config_filename
            cls._instance.path.parent.mkdir(parents=True, exist_ok=True)
            cls._instance.default_path = resolved_default_path
            cls._instance.lock = FileLock(str(cls._instance.path) + ".lock")
            cls._instance.lock_timeout = lock_timeout
            cls._instance.load()

        return cls._instance

    def __init__(self, path: str | Path, default_path: str | Path | None = None, lock_timeout: int = 5):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.default_path = Path(default_path) if default_path is not None else None
        self.lock = FileLock(str(self.path) + ".lock")
        self.lock_timeout = lock_timeout
        self._defaults: dict[str, JSONValue] = {}
        self._data: dict[str, JSONValue] = {}
        self.load()

    def load(self) -> bool:
        """Load settings from disk and merge them with defaults."""
        defaults = self._load_json(self.default_path) if self.default_path is not None else {}
        self._defaults = defaults
        data_dir = self.dirs.user_data_path
        log_dir = self.dirs.user_log_path
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._defaults["data_dir"] = str(data_dir)
        self._defaults["log_dir"] = str(log_dir)

        try:
            self.lock.acquire(timeout=self.lock_timeout)
            try:
                if not self.path.exists():
                    self._data = dict(defaults)
                    self.save()
                    return False

                user_config = self._load_json(self.path)
                self._data = dict(defaults)
                self._data.update(user_config)
            finally:
                with contextlib.suppress(Exception):
                    self.lock.release()
        except Timeout:
            try:
                user_config = self._load_json(self.path)
                self._data = dict(defaults)
                self._data.update(user_config)
            except (PermissionError, json.JSONDecodeError):
                self._data = dict(defaults)
                return False
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = dict(defaults)
            self.save()
            return False
        return True

    def save(self) -> None:
        """Persist current settings to disk atomically."""
        self._write_json(self._data)

    def get(self, key: str, default: JSONValue | None = None) -> JSONValue | None:
        """Return a stored setting value or a fallback default."""
        return self._data.get(key, default)

    def set(self, key: str, value: JSONValue) -> None:
        """Store a setting value and persist it to disk."""
        self._data[key] = value
        self.save()

    def remove(self, key: str) -> None:
        """Remove a stored setting entry if it exists."""
        if key in self._data:
            del self._data[key]
            self.save()

    def update(self, values: dict[str, JSONValue]) -> None:
        """Update multiple settings values and persist them to disk."""
        self._data.update(values)
        self.save()

    def set_defaults(self, defaults: dict[str, Any]) -> None:
        """Set default values from a dict and refresh the live data."""
        self._defaults = dict(defaults)
        merged = dict(self._defaults)
        merged.update(self._data)
        self._data = merged
        self.save()

    def as_dict(self) -> dict[str, JSONValue]:
        """Return a shallow copy of the current settings."""
        return dict(self._data)

    def __getitem__(self, key: str) -> JSONValue:
        """Return a setting value using mapping syntax."""
        return self._data[key]

    def __setitem__(self, key: str, value: JSONValue) -> None:
        """Store a setting value using mapping syntax."""
        self.set(key, value)

    def __contains__(self, key: object) -> bool:
        """Return whether a key exists in the current settings."""
        return key in self._data

    def __iter__(self) -> Iterator[str]:
        """Iterate over the current setting keys."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return the number of currently stored settings."""
        return len(self._data)

    def items(self) -> ItemsView[str, JSONValue]:
        """Return the current settings as key/value items."""
        return self._data.items()

    def keys(self) -> Iterable[str]:
        """Return the current setting keys."""
        return self._data.keys()

    def values(self) -> Iterable[JSONValue]:
        """Return the current setting values."""
        return self._data.values()

    def _write_json(self, data: dict[str, JSONValue], path: Path | None = None) -> None:
        """Write dict data to json file."""
        target = path or self.path
        temp_path = target.with_suffix(target.suffix + ".tmp")
        try:
            self.lock.acquire(timeout=self.lock_timeout)
            try:
                with temp_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                Path.replace(temp_path, target)
            finally:
                with contextlib.suppress(Exception):
                    self.lock.release()
        except Timeout:
            with contextlib.suppress(Exception):
                with temp_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                Path.replace(temp_path, target)
        finally:
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    @staticmethod
    def _load_json(path: Path | None) -> dict[str, JSONValue]:
        """Return dict form json file."""
        if path is None or not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
