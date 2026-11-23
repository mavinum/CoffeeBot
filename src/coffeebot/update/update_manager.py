"""
Manage updates if newer version is available on PyPi.

UpdateManager handles the execution of an update via ``uv tool upgrade``
in the background with subsequent restarting of the app.
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

import subprocess
from collections.abc import Callable

from loguru import logger
from PyQt6.QtCore import QThread, pyqtSignal

from coffeebot.config.settings import Settings


class UpdateManager(QThread):
    """Thread to handle app update and restart."""

    upgrade_started = pyqtSignal()  # ty: ignore[missing-argument]
    upgrade_completed = pyqtSignal()  # ty: ignore[missing-argument]
    upgrade_failed = pyqtSignal(str)  # ty: ignore[missing-argument]
    upgrade_finished = pyqtSignal()  # ty: ignore[missing-argument]

    def __init__(self, on_restart: Callable | None = None):
        super().__init__()
        self.on_restart = on_restart
        self.settings = Settings.get_instance()

    def run(self) -> None:
        """Run update via uv tool in the background."""
        self.upgrade_started.emit()
        app_name = self.settings.app_name
        if not app_name:
            error_msg = "App name is not configured for update management."
            logger.error(error_msg)
            self.upgrade_failed.emit(error_msg)
            return

        try:
            result: subprocess.CompletedProcess = subprocess.run(
                ["uv", "tool", "install", "--upgrade", app_name],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                shell=False,
            )
            if result.returncode == 0:
                self.upgrade_completed.emit()
                self.upgrade_finished.emit()
                return

            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error occurred during upgrade"
            logger.error(f"Upgrade failed: {error_msg}")
            self.upgrade_failed.emit(error_msg)
        except subprocess.TimeoutExpired as exc:
            error_msg = f"Upgrade timed out after 5 minutes: {exc}"
            logger.error(error_msg)
            self.upgrade_failed.emit(error_msg)
        except Exception as exc:
            error_msg = f"Upgrade failed: {exc}"
            logger.error(error_msg)
            self.upgrade_failed.emit(error_msg)

    def trigger_restart(self) -> None:
        """Restart app after successful upgrade."""
        if self.on_restart is not None:
            self.on_restart()
