"""
################################################################################

Main GUI module for the CoffeeBot interface.

Important: Custom GUI Widgets are included in the ui-file via Widget promotion
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
import os
import sys
import typing
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import cast

from loguru import logger
from PyQt6 import uic
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QMovie, QPixmap
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QPushButton, QScroller, QTableWidgetItem

from coffeebot.config.settings import Settings
from coffeebot.db.users import Rating, UserDB
from coffeebot.gui.widgets.custom_widgets import PriceItem
from coffeebot.system.webdav_manager import Action, WebDavManager
from coffeebot.update.update_check import UpdateChecker
from coffeebot.update.update_manager import UpdateManager

basedir = Path(__file__).parent

MainWindowUI, _ = uic.loadUiType(basedir / "main_window.ui")


class CoffeeBot(QMainWindow, MainWindowUI):
    """Main Window ui for the CoffeeBot."""

    def __init__(self):
        super().__init__()
        self.config = Settings.get_instance()
        self.user_id = None
        self.db = UserDB(Path(str(self.config.get("data_dir")), str(self.config.get("db_file"))))
        self.db.connect()
        self._auth_target = None
        self.webdav_manager: WebDavManager | None = None

        self._newer_version: str | None = None
        self._upgrade_in_progress = False

        self.locked = True
        self.lock_timer = QTimer(self)
        self.lock_timer.setSingleShot(True)
        self.lock_timer.timeout.connect(self._lock)

        self.init_ui()
        self.load_ui_data()

        self._enjoy_gif: QMovie = QMovie(str(basedir / "icons" / "enjoy_gif.gif"), parent=self)
        self._gif_timer = QTimer()

        if bool(self.config.get("auto_check_update", False)):
            self._init_updater()
        else:
            logger.info("Automatic update checks are disabled - updater not started")

        self._configure_webdav()

        self.bot_status_label.setText("Coming soon")

    def init_ui(self) -> None:  # noqa: PLR0915
        """Inizialize UI and UI elements."""
        self.setupUi(self)

        #  Set window attributes and position
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        width = QGuiApplication.primaryScreen().availableGeometry().width()  # ty:ignore[unresolved-attribute]
        height = QGuiApplication.primaryScreen().availableGeometry().height()  # ty:ignore[unresolved-attribute]

        if width < 1300 and height < 900:
            # self.showFullScreen()
            self.setFixedSize(width, height)
        else:
            self.setFixedSize(1280, 800)
            self.move(0, 0)

        self.icons_text_widget.hide()
        self.home_button.setChecked(True)

        # Signals and Slots
        self.user_table.cellClicked.connect(self._select_user)
        self.user_table.currentCellChanged.connect(self._select_user)
        QScroller.grabGesture(self.user_table, QScroller.ScrollerGestureType.TouchGesture)

        self.cat_1_button.clicked.connect(self._bill)
        self.cat_2_button.clicked.connect(self._bill)
        self.cat_3_button.clicked.connect(self._bill)

        self.home_button.clicked.connect(self._switch)
        self.add_user_button.clicked.connect(self._switch)
        self.edit_user_button.clicked.connect(self._switch)
        self.edit_info_button.clicked.connect(self._switch)
        self.reset_challenge_button.clicked.connect(self._switch)
        self.settings_button.clicked.connect(self._switch)
        self.lock_button.toggled.connect(self._toggle_lock)
        self.update_button.clicked.connect(self._switch)
        self.update_button.setVisible(False)

        # Widgets signals and slots
        self.add_user_widget.user_db = self.db
        self.edit_user_widget.user_db = self.db

        self.edit_user_widget.save_signal.connect(self._on_user_edited)
        self.edit_user_widget.delete_signal.connect(self._on_user_edited)
        self.edit_user_widget.cancel_signal.connect(self._on_user_edited)

        self.add_user_widget.save_signal.connect(self._on_user_edited)
        self.add_user_widget.cancel_signal.connect(self._on_user_edited)

        self.authentication_widget.cancel_signal.connect(self._return_home)
        self.authentication_widget.confirm_signal.connect(self.grant_access)

        self.edit_info_widget.cancel_signal.connect(self._return_home)
        self.edit_info_widget.confirm_signal.connect(self._update_info)

        self.reset_challenge_widget.cancel_signal.connect(self._return_home)
        self.reset_challenge_widget.confirm_signal.connect(self._update_challenge)
        self.cheer_button.clicked.connect(self._return_home)
        self.thanks_button.clicked.connect(self._return_home)

        self.settings_widget.set_db(self.db)
        self.settings_widget.cancel_signal.connect(self._on_settings_saved)
        self.settings_widget.save_signal.connect(self._on_settings_saved)
        self.settings_widget.restart_signal.connect(self.restart_app)
        self.settings_widget.close_signal.connect(self.close)

        # WebDAV integration
        self.settings_widget.backup_button.clicked.connect(self._trigger_manual_backup)
        self.settings_widget.webdav_settings_applied.connect(self._configure_webdav)
        self.settings_widget.webdav_export.connect(self._trigger_export_upload)

        # Update integration
        self.settings_widget.update_check_button.clicked.connect(self._check_for_update)
        self.settings_widget.update_now_button.clicked.connect(self._start_upgrade)
        self.settings_widget.update_now_button.hide()

        self.settings_widget.challenge_link_button.clicked.connect(
            lambda: (self.reset_challenge_widget.load(), self.main_stack.setCurrentWidget(self.reset_challenge_page))
        )
        self.settings_widget.info_link_button.clicked.connect(
            lambda: (self.edit_info_widget.load(), self.main_stack.setCurrentWidget(self.edit_info_page))
        )

    def _init_updater(self) -> None:
        """Initialize updater for version checking and upgrading."""
        self.update_checker = UpdateChecker(
            check_interval=24 * 3600, auto_check=bool(self.config.get("auto_check_update"))
        )
        self.update_checker.update_available.connect(self._notify_update_available)
        self.update_checker.error.connect(self._on_update_error)
        self.update_checker.up_to_date.connect(self._on_up_to_date)
        self.update_checker.start()

        self._create_update_manager()

    def load_ui_data(self) -> None:
        """Load ui configuration form settings."""
        self._load_table()

        # Labels and ui-elements
        self.cat_1_button.setText(f"{self.config['cat_1_price']:.2f} \u20ac")
        self.cat_2_button.setText(f"{self.config['cat_2_price']:.2f} \u20ac")
        self.cat_3_button.setText(f"{self.config['cat_3_price']:.2f} \u20ac")

        items = self.config.get("cat_1_items", [])
        if isinstance(items, (list, tuple)):
            self.cat_1_item_label.setText("\n".join(str(i) for i in items))
        else:
            self.cat_1_item_label.setText(str(items))

        items = self.config.get("cat_2_items", [])
        if isinstance(items, (list, tuple)):
            self.cat_2_item_label.setText("\n".join(str(i) for i in items))
        else:
            self.cat_2_item_label.setText(str(items))

        items = self.config.get("cat_3_items", [])
        if isinstance(items, (list, tuple)):
            self.cat_3_item_label.setText("\n".join(str(i) for i in items))
        else:
            self.cat_3_item_label.setText(str(items))

        #  Set logo
        logo_file = Path(self.config["data_dir"], self.config["logo_file"])
        pixmap = QPixmap(str(logo_file))
        if pixmap.isNull():
            fallback_logo = files("coffeebot").joinpath("ressources", "icons", "icon.svg")
            pixmap = QPixmap(str(fallback_logo))

        if pixmap.isNull():
            self.logo.clear()
        else:
            self.logo.setPixmap(pixmap.scaled(300, 70, Qt.AspectRatioMode.KeepAspectRatio))

        # Info text
        self._update_info(home=False)

        # Challenge
        self._update_challenge(home=False)

    def _load_table(self) -> None:
        """Fill table with user data form database."""
        logger.debug("Loading table....")
        self.user_table.setRowCount(1)
        for i, user in enumerate(self.db.get_users()):
            if self.user_table.rowCount() - 1 < i:
                self.user_table.insertRow(i)
            _id = QTableWidgetItem()
            _id.setTextAlignment(Qt.AlignmentFlag.AlignVCenter + Qt.AlignmentFlag.AlignRight)
            _id.setData(Qt.ItemDataRole.DisplayRole, user[0])
            self.user_table.resizeColumnToContents(0)
            self.user_table.setItem(i, 0, _id)
            self.user_table.setItem(i, 1, QTableWidgetItem(f"{user[1]} {user[2]}"))
            self.user_table.resizeColumnToContents(1)

            balance = PriceItem(f"{float(user[6]):.2f} \u20ac")
            self.user_table.setItem(i, 2, balance)

    def _select_user(self, row) -> None:
        """Select user and display name and debt in the purchase window."""
        try:
            self.user_id = self.user_table.item(row, 0).text()
        except AttributeError:
            return
        user = self.db.get_user(self.user_id)
        balance = float(user.balance)

        self.user_label.setText(f"{user.forename} {user.surename}")
        self.user_balance.setText(f"{balance:.2f} \u20ac")

        rating = Rating.get_rating(balance)
        self.rating_label.setText(str(rating))

    def _deselect_user(self) -> None:
        """Remove user selection to avoid accidental double billing."""
        self.user_id = None
        self.user_table.clearSelection()
        self.user_label.setText("not selected")
        self.user_balance.setText("")
        self.rating_label.setText("")

    def _bill(self) -> None:
        """Add button price to bill."""
        if self.user_id is None:
            return

        category = self.sender().objectName().strip("_button")  # ty:ignore[unresolved-attribute]
        price = self.config[f"{category}_price"]
        self.db.bill(self.user_id, category, price)
        self._show_enjoy_gif()
        self._load_table()

        self._deselect_user()

        if self.config["tracked_categories"][category]:
            self._add_progress()

    def _show_enjoy_gif(self) -> None:
        """Play the purchase animation once, clearing it when finished."""
        self._enjoy_gif.setScaledSize(self.gif_label.size())

        self.gif_label.setMovie(self._enjoy_gif)
        self._enjoy_gif.start()
        self._gif_timer.singleShot(4000, lambda: (self._enjoy_gif.stop(), self.gif_label.clear()))

    def _add_progress(self, increment: int = 1) -> None:
        """Increment challenge progressbar by specified value."""
        new_val = self.config["challenge_current"] + increment
        if new_val <= self.config["challenge_goal"]:
            self.challenge_bar.setValue(new_val)
            self.config["challenge_current"] = new_val

        if new_val == self.config["challenge_goal"]:
            self.reward_label.setText(self.config["selected_reward"])
            self.main_stack.setCurrentWidget(self.winner_page)

    def _switch(self) -> None:
        """Switch main widget according to sidebar button."""
        btn = self.sender()
        if btn is None:
            return
        btn = cast("QPushButton", btn)

        if self.lock_timer.isActive():
            self.lock_timer.stop()

        match btn.objectName():
            case "home_button":
                self.main_stack.setCurrentWidget(self.home_page)
                self._start_lock_timeout()
            case "add_user_button":
                self.main_stack.setCurrentWidget(self.add_user_page)
            case "edit_user_button":
                if self.user_id is None:
                    self.home_button.setChecked(True)
                    self.home_button.clicked.emit()
                    return
                self.edit_user_widget.set_user(self.db.get_user(self.user_id))
                if self.locked:
                    self._auth_target = self.edit_user_page
                    self.main_stack.setCurrentWidget(self.authentication_page)
                    self.authentication_widget.password_edit.setFocus()
                else:
                    self.main_stack.setCurrentWidget(self.edit_user_page)
            case "edit_info_button":
                self.edit_info_widget.load()
                self.main_stack.setCurrentWidget(self.edit_info_page)
            case "reset_challenge_button":
                self.reset_challenge_widget.load()
                if self.locked:
                    self._auth_target = self.reset_challenge_page
                    self.main_stack.setCurrentWidget(self.authentication_page)
                    self.authentication_widget.password_edit.setFocus()
                else:
                    self.main_stack.setCurrentWidget(self.reset_challenge_page)
            case "settings_button":
                self.settings_widget.load()
                self.settings_widget.tabWidget.setCurrentWidget(self.settings_widget.general_tab)
                if self.locked:
                    self._auth_target = self.settings_page
                    self.main_stack.setCurrentWidget(self.authentication_page)
                    self.authentication_widget.password_edit.setFocus()
                else:
                    self.main_stack.setCurrentWidget(self.settings_page)
            case "update_button":
                self.settings_widget.load()
                self.settings_widget.tabWidget.setCurrentWidget(self.settings_widget.update_tab)
                if self.locked:
                    self._auth_target = self.settings_page
                    self.main_stack.setCurrentWidget(self.authentication_page)
                    self.authentication_widget.password_edit.setFocus()

    # region authentication

    def _start_lock_timeout(self) -> None:
        """Start timer to lock app after timeout."""
        if self.locked:
            return
        if self.lock_timer.isActive():
            self.lock_timer.start()
        timeout = int(self.config.get("lock_timeout", 60)) * 1000
        self.lock_timer.setInterval(timeout)
        self.lock_timer.start()

    def _lock(self) -> None:
        """Lock restricted features and stop the unlock timer."""
        if self.locked:
            return
        self.locked = True
        self.lock_timer.stop()
        self.lock_button.blockSignals(True)
        self.lock_button.setChecked(False)
        self.lock_button.blockSignals(False)
        self._return_home()

    def _unlock(self) -> None:
        """Unlock restricted features and start the auto-lock timer."""
        self.locked = False
        self.lock_button.blockSignals(True)
        self.lock_button.setChecked(True)
        self.lock_button.blockSignals(False)

    def _toggle_lock(self, checked: bool) -> None:
        """Handle manual lock/unlock via the lock button."""
        if checked:
            if self.locked:
                self._auth_target = None
                self.main_stack.setCurrentWidget(self.authentication_page)
                self.authentication_widget.password_edit.setFocus()
            else:
                self._unlock()
        else:
            self._lock()

    def grant_access(self) -> None:
        """Validate entered password and unlock restricted features."""
        self._unlock()
        if self._auth_target is not None:
            self.main_stack.setCurrentWidget(self._auth_target)
            self._auth_target = None
            return
        self._start_lock_timeout()

        self._return_home()

    # endregion

    # region Main GUI callbacks

    def _on_settings_saved(self) -> None:
        """Reload gui after settings have changed."""
        self.load_ui_data()
        self._return_home()
        self._start_lock_timeout()

    def _on_user_edited(self) -> None:
        """Handle user edited signals from edit_user_widget."""
        self._load_table()
        self._deselect_user()
        self._return_home()
        self._start_lock_timeout()

    @typing.override
    def _update_info(self, home: bool = True) -> None:
        """Reload info field text on home page."""
        text: str = self.config["info_text"]
        self.info_field.setHtml(text)
        if home:
            self._return_home()

    @typing.override
    def _update_challenge(self, home: bool = True) -> None:
        """Update progressbar for coffee challenge."""
        self.challenge_bar.setRange(0, self.config["challenge_goal"])
        self.challenge_bar.setValue(self.config["challenge_current"])
        if home:
            self._return_home()

    def _return_home(self) -> None:
        """Switch back to home screen."""
        self.home_button.clicked.emit()
        self.home_button.setChecked(True)
        if self.locked and self.lock_button.isChecked():
            self.lock_button.blockSignals(True)
            self.lock_button.setChecked(False)
            self.lock_button.blockSignals(False)
        self._start_lock_timeout()

    # endregion

    # region WebDAV callbacks
    def _configure_webdav(self) -> None:
        """Apply the persisted WebDAV configuration to the manager lifecycle."""
        if not bool(self.config.get("webdav_enabled", False)):
            if self.webdav_manager is not None:
                self.webdav_manager.stop_auto_backup()
                self.webdav_manager = None
            self._show_webdav_status("WebDAV backup manager is disabled")
            logger.info("WebDAV backup manager is disabled")
            return

        if self.webdav_manager is None:
            self.webdav_manager = WebDavManager()
            self.webdav_manager.backup_progress.connect(self._show_webdav_status)
            self.webdav_manager.backup_finished.connect(self._show_webdav_result)
            self.webdav_manager.export_finished.connect(self._show_export_result)

        self.webdav_manager.stop_auto_backup()  # sure?
        if bool(self.config.get("auto_backup_enabled", False)):
            interval = int(self.config.get("backup_interval", 24))
            self.webdav_manager.start_auto_backup(interval)
            self._show_webdav_status(f"WebDAV auto-backup started every {interval}h.")
            logger.info(f"WebDAV auto-backup started every {interval}h.")
        else:
            self._show_webdav_status("WebDAV enabled, but auto-backup is disabled.")
            logger.info("WebDAV enabled, but auto-backup is disabled.")
        self.webdav_manager.check_connection()

    def _show_webdav_status(self, message: str) -> None:
        """Display active WebDAV backup progress."""
        self.settings_widget.webdav_status_label.setText(message)

    def _show_webdav_result(self, success: bool, message: str) -> None:
        """Display the final WebDAV result and preserve errors visibly."""
        if success:
            timestamp = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M")
            self.settings_widget.webdav_status_label.setText(f"Last update: {timestamp}")
            logger.info(message)
        else:
            self.settings_widget.webdav_status_label.setText(message)
            logger.error(message)

    def _show_export_result(self, success: bool, message: str) -> None:
        """Display final WebDAV export data upload results."""
        if success:
            self.settings_widget.export_status_label.setText("Export successfully uploaded!")
            logger.info(message)
        else:
            self.settings_widget.export_status_label.setText(message)
            logger.error(message)

    def _trigger_manual_backup(self) -> None:
        """Trigger a manual backup if manager is available."""
        if self.webdav_manager:
            self.settings_widget.webdav_status_label.setText("Starting backup...")
            self.webdav_manager.perform_upload(Action.BACKUP)
        else:
            self.settings_widget.webdav_status_label.setText("WebDAV is not configured")

    def _trigger_export_upload(self, file: Path) -> None:
        """Trigger upload of exported data."""
        if self.webdav_manager:
            self.settings_widget.export_status_label.setText("Starting upload....")
            self.webdav_manager.perform_upload(Action.EXPORT, file)
        else:
            self.settings_widget.export_status_label.setText("WebDAV is not configured")

    # endregion

    # region Updater callbacks

    def _create_update_manager(self) -> None:
        """Create a fresh UpdateManager and wire UI callbacks."""
        self.update_manager = UpdateManager(self.restart_app)
        self.update_manager.upgrade_started.connect(lambda: logger.info("Upgrade started"))
        self.update_manager.upgrade_completed.connect(self._on_upgrade_completed)
        self.update_manager.upgrade_failed.connect(self._on_upgrade_failed)
        self.update_manager.upgrade_finished.connect(lambda: logger.info("Upgrade finished"))

    def _start_upgrade(self) -> None:
        """Trigger the upgrade process."""
        if self._upgrade_in_progress:
            return

        if self.update_manager.isRunning():
            return

        if self._newer_version is None:
            return

        if self.update_manager.isFinished():
            self._create_update_manager()

        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"Install update {self._newer_version} and restart the application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._upgrade_in_progress = True
        self.settings_widget.update_check_button.setEnabled(False)
        self.settings_widget.update_now_button.setEnabled(False)
        self.update_manager.start()

    def _check_for_update(self) -> None:
        """Perform a manual update check from the settings update tab."""
        if self._upgrade_in_progress:
            return

        self.settings_widget.update_status_label.setText("Checking for updates...")
        self.settings_widget.update_now_button.hide()
        self.update_checker.request_check()

    def _notify_update_available(self, version: str) -> None:
        """Handle an available update from the background checker."""
        self._newer_version = version
        self.update_button.show()
        logger.info(f"Update available: {version}")
        self.settings_widget.update_status_label.setText(f"Update available: {version}")
        self.settings_widget.update_now_button.show()

    def _on_update_error(self, error: str) -> None:
        """Handle update check failures."""
        self.settings_widget.update_status_label.setText(f"Update check failed: {error}")
        self.settings_widget.update_now_button.hide()

    def _on_up_to_date(self, msg: str) -> None:
        """Update the button state after an update check completes."""
        if self._newer_version is None:
            self.settings_widget.update_status_label.setText(msg)
            self.settings_widget.update_now_button.hide()

        if self._newer_version is None and not self._upgrade_in_progress:
            self.update_button.hide()

    def _on_upgrade_completed(self) -> None:
        """Handle a successful upgrade."""
        self._upgrade_in_progress = False
        QMessageBox.information(
            self, "Upgrade Complete", "The application was upgraded successfully and will now restart."
        )
        self.settings_widget.update_check_button.setEnabled(True)
        self.settings_widget.update_now_button.setEnabled(True)
        self.settings_widget.update_now_button.hide()
        self.restart_app()

    def _on_upgrade_failed(self, message: str) -> None:
        """Handle a failed upgrade attempt."""
        self._upgrade_in_progress = False
        QMessageBox.critical(self, "Upgrade Failed", f"Upgrade failed: {message}")
        self.settings_widget.update_check_button.setEnabled(True)
        self.settings_widget.update_now_button.setVisible(self._newer_version is not None)

    # endregion

    def restart_app(self) -> None:
        """Restart application to apply upgrade changes."""
        with contextlib.suppress(Exception):
            self.update_checker.stop()
        if self.webdav_manager is not None:
            self.webdav_manager.stop()
        self.db.close()

        os.execv(sys.executable, [sys.executable, *sys.argv])  # noqa: S606

    def closeEvent(self, event) -> None:  # noqa: N802  # ty:ignore[invalid-method-override]
        """Cleanup before closing."""
        if self.webdav_manager is not None:
            self.webdav_manager.stop()
        self.db.close()
        super().closeEvent(event)
