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

import shutil
from importlib.metadata import distribution
from pathlib import Path

from loguru import logger

PKG_NAME = "coffeebot"
APP_NAME = "CoffeeBot"
ICON_NAME = "icon.svg"


def create_shortcut() -> bool:
    """
    Create a .desktop file on the user's desktop.

    Assumes the application is installed via `uv tool install`.
    The shortcut points to the 'coffeebot' binary in the uv bin directory
    and uses 'icon.svg' from the installed package directory.
    """
    try:
        executable = shutil.which("coffeebot")
        if not executable:
            logger.error("Could not find 'coffeebot' binary in PATH.")
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
            f"Exec={executable}",
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
