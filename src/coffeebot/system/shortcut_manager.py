"""
################################################################################

Desktop Shortcut Manager for CoffeeBot.

This module provides the `ShortcutManager` class which creates a .desktop file
on the user's desktop to launch the CoffeeBot application. It is designed to
work with installations performed via `uv tool install`.

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

import os
import shutil
from importlib.metadata import distribution
from pathlib import Path

from loguru import logger

from coffeebot.config.settings import Settings
from coffeebot.system.systemd_manager import SystemdManager

PKG_NAME = "coffeebot"
APP_NAME = "CoffeeBot"
ICON_NAME = "icon.svg"
LAUNCHER_NAME = "coffeebot-launch"


def _find_executable(name: str) -> str | None:
    """Find an installed executable, including uv's default user bin directory."""
    executable = shutil.which(name)
    if executable:
        return executable

    uv_executable = Path.home() / ".local" / "bin" / name
    return str(uv_executable) if uv_executable.is_file() else None


def launch_app() -> int:
    """Restart the configured systemd service or launch CoffeeBot directly."""
    Settings.configure_app("Coffeebot", "Mavinum")
    manager = SystemdManager()

    if manager.service_exists and (manager.service_running or manager.service_enabled):
        success, message = manager.restart()
        if success:
            logger.info("Restarted CoffeeBot systemd service.")
            return 0
        logger.error(f"Could not restart CoffeeBot systemd service: {message}")
        return 1

    executable = _find_executable(PKG_NAME)
    if not executable:
        logger.error("Could not find the 'coffeebot' executable in PATH or ~/.local/bin.")
        return 1

    logger.info("No active or enabled CoffeeBot systemd service; launching the application.")
    try:
        os.execv(executable, [executable])  # noqa: S606
    except OSError as exc:
        logger.error(f"Could not launch CoffeeBot: {exc}")
        return 1
    return 0


def create_shortcut() -> bool:
    """
    Create a .desktop file on the user's desktop.

    Assumes the application is installed via `uv tool install`.
    The shortcut points to the service-aware launcher in the uv bin directory
    and uses 'icon.svg' from the installed package directory.
    """
    try:
        launcher = _find_executable(LAUNCHER_NAME)
        if not launcher:
            logger.error(f"Could not find '{LAUNCHER_NAME}' binary in PATH or ~/.local/bin.")
            return False
        try:
            package_path = Path(str(distribution(PKG_NAME).locate_file(""))).parent
            icon_path = package_path / ICON_NAME

            if not icon_path.exists():
                icon_files = list(package_path.glob(f"**/{ICON_NAME}"))
                if not icon_files:
                    logger.error("No icon file found. Shortcut will have no icon.")
                icon_path = icon_files[0]
        except Exception as e:
            logger.error(f"Error finding package path: {e}")
            icon_path = None
            return False

        shortcut_name = f"{APP_NAME}.desktop"
        application_path = Path.home() / ".local" / "share" / "applications" / shortcut_name
        application_path.parent.mkdir(parents=True, exist_ok=True)
        shortcut_path = Path.home() / "Desktop" / shortcut_name
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)

        content = [
            "[Desktop Entry]",
            f"Name={APP_NAME}",
            f"Exec={launcher}",
            f"Icon={icon_path}" if icon_path and icon_path.exists() else "",
            "Type=Application",
            "Terminal=false",
            "Categories=Utility;Office;",
            "Comment=Coffee and beverage billing system",
        ]

        content = [line for line in content if line]

        with shortcut_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(content))
        shortcut_path.chmod(0o755)

        with application_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(content))
        application_path.chmod(0o755)

        logger.info("Desktop shortcut created")

    except Exception as e:
        logger.error(f"Failed to create desktop shortcut: {e}")
        return False
    else:
        return True
