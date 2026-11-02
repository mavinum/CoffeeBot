"""
################################################################################

Entry point for startup of the coffeebot application.

Setup of basic configuration including:
    - logging configuration
    - loading of user defined settings
Starting CoffeeBot in production mode

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

import sys
from importlib.resources import files
from pathlib import Path

from loguru import logger
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from coffeebot.config.settings import Settings
from coffeebot.gui.main_window import CoffeeBot

# region Logging setup


def init_logger(log_dir: Path, level: str) -> None:
    """Create logger with corresponding rotating file handler."""
    logger.remove()
    # Add file sink
    logger.add(
        Path(log_dir, "coffeebot.log"),
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:^9} | {module:10s}:{function:10s}:{line:4} - {message}",
        level=level,
        rotation="monthly",
        backtrace=False,
        diagnose=False,
    )
    # Add additional stream sink
    logger.add(
        sys.stderr,
        format="<g>{time:HH:mm:ss}</g> | <level>{level:^9}</level> | {module}.{function:10s}: {line:4} - <level>{message}</level>",
        level="TRACE",
        backtrace=True,
        diagnose=True,
    )


def handle_exception(exc_type, exc_value, exc_tb) -> None:
    """Handle uncought exceptions and log them via defined logger."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.opt(depth=1, exception=(exc_type, exc_value, exc_tb)).error("Unhandled exception")
    sys.exit(1)


# endregion


def main() -> None:  # noqa: D103
    Settings.configure_app("Coffeebot", "Mavinum")
    settings = Settings.get_instance()

    init_logger(Path(str(settings["log_dir"])), str(settings["log_level"]))
    sys.excepthook = handle_exception
    logger.info(
        "\n****************************************\nCoffeebot startup\n****************************************"
    )

    # defaultfont = QFont("Roboto", 10)
    app = QApplication(sys.argv)
    app.setApplicationName("CoffeeBot")
    app.setApplicationDisplayName("CoffeeBot")
    app.setOrganizationName("Mavinum")
    app.setDesktopFileName("CoffeeBot")
    app.setWindowIcon(QIcon(str(files("coffeebot").joinpath("ressources", "icons", "icon.svg"))))
    # app.setFont(defaultfont)
    app.setStyle("Fusion")
    ex = CoffeeBot()
    ex.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
