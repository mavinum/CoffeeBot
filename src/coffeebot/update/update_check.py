"""
Check if new version is available.

UpdateChecker compares the installed app version with the lastest
version available on PyPi and sends update notification.
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

import asyncio
import threading

import httpx
from loguru import logger
from packaging import version as package_version
from PyQt6.QtCore import QThread, pyqtSignal

from coffeebot.config.settings import Settings


class UpdateChecker(QThread):
    """Thread to check for new version on PyPi in the background."""

    update_available = pyqtSignal(str)  # ty: ignore[missing-argument]
    error = pyqtSignal(str)  # ty: ignore[missing-argument]
    up_to_date = pyqtSignal(str)  # ty: ignore[missing-argument]

    def __init__(self, check_interval: int = 3600, auto_check: bool = True):  # noqa: FBT002
        super().__init__()
        self.check_interval = check_interval
        self.running = True
        self.auto_check = auto_check
        self.latest_version: str | None = None
        self.settings = Settings.get_instance()
        self._check_requested = threading.Event()

    def run(self) -> None:
        """Check for updates continuously."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if self.auto_check:
            self._run_check(loop)

        while self.running:
            timeout = float(self.check_interval) if self.auto_check else None
            if self._check_requested.wait(timeout=timeout):
                self._check_requested.clear()
                self._run_check(loop)
            elif self.auto_check:
                self._run_check(loop)

        loop.close()

    def _run_check(self, loop: asyncio.AbstractEventLoop) -> None:
        try:
            latest = loop.run_until_complete(self._fetch_latest_version())
        except Exception as exc:
            self.error.emit("Failed to fetch versions from PyPi")
            logger.error(f"Update check failed: {exc}")
            return

        if latest is None:
            self.up_to_date.emit("Couldn't retrieve release versions.")
            return

        try:
            is_newer = self._is_newer(latest)
        except Exception as exc:
            self.error.emit(str(exc))
            logger.error(f"Failed to compare package versions: {exc}")
            return
        if is_newer:
            self.latest_version = latest
            self.update_available.emit(latest)
            return
        self.up_to_date.emit(f"No update available; current version {self.settings.version} is up to date.")

    def request_check(self) -> None:
        """Request an immediate update check."""
        self._check_requested.set()

    async def _fetch_latest_version(self) -> str | None:
        """Fetch latest available app version from PyPi."""
        app = Settings.app_name or self.settings.app_name
        if not app:
            error_message = "App name is not configured for update checking."
            logger.error(error_message)
            self.error.emit(error_message)
            return None

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://pypi.org/pypi/{app}/json")
            response.raise_for_status()
            return response.json()["info"]["version"]

    def _is_newer(self, latest: str) -> bool:
        """Check if latest version is newer than current version."""
        current_version = self.settings.version
        if not current_version:
            msg = "Current app version is not configured for update checking."
            raise ValueError(msg)

        return package_version.parse(latest) > package_version.parse(current_version)

    def stop(self) -> None:
        """Stop thread gracefully."""
        self.running = False
        self._check_requested.set()
        self.wait()
