"""
################################################################################

Settings widget to manage user and applciation settings.

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

import csv
import os
import shutil
import tempfile
import time
import typing
import webbrowser
from pathlib import Path
from typing import Any

from loguru import logger
from openpyxl import Workbook
from PyQt6 import uic
from PyQt6.QtCore import QDir, QSignalBlocker, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QFileDialog, QLineEdit, QSpinBox, QTextEdit, QWidget

from coffeebot.auth import set_master_password
from coffeebot.config.settings import Settings
from coffeebot.db.statistics import StatsRepo
from coffeebot.db.users import UserDB
from coffeebot.system.credential_store import CredentialStoreError, get_webdav_credential, store_webdav_credential
from coffeebot.system.systemd_manager import SystemdManager

basedir = Path(__file__).parent
style_path = basedir / "widget_styles.qss"
QDir.addSearchPath("coffeebot-icons", str(basedir.parent / "icons"))

SettingsWidgetUI, _ = uic.loadUiType(basedir / "settings_widget.ui")

with style_path.open("r", encoding="utf-8") as style_file:
    WIDGET_STYLE = style_file.read()


class SettingsWidget(QWidget, SettingsWidgetUI):
    """Editor Widget for all coffeebot settings."""

    cancel_signal = pyqtSignal()  # ty: ignore[missing-argument]
    save_signal = pyqtSignal()  # ty: ignore[missing-argument]
    restart_signal = pyqtSignal()  # ty: ignore[missing-argument]
    close_signal = pyqtSignal()  # ty: ignore[missing-argument]
    webdav_settings_applied = pyqtSignal()  # ty: ignore[missing-argument]
    webdav_export = pyqtSignal(str)  # ty: ignore[missing-argument]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)  # ty: ignore[invalid-argument-type]
        self.setupUi(self)
        self.setStyleSheet(WIDGET_STYLE)
        self.manager = SystemdManager()

        self._config = Settings.get_instance()
        self._db: UserDB | None = None

        self._bindings: dict[str, Any] = {
            "cat_1_price": getattr(self, "cat_1_price_spin", None),
            "cat_1_items": getattr(self, "cat_1_item_edit", None),
            "cat_2_price": getattr(self, "cat_2_price_spin", None),
            "cat_2_items": getattr(self, "cat_2_item_edit", None),
            "cat_3_price": getattr(self, "cat_3_price_spin", None),
            "cat_3_items": getattr(self, "cat_3_item_edit", None),
            # "autostart": getattr(self, "autostart_check", None),
            "auto_restart": getattr(self, "restart_check", None),
            "auto_check_update": getattr(self, "auto_update_checkbox", None),
            "auto_backup_enabled": getattr(self, "auto_backup_check", None),
            "webdav_enabled": getattr(self, "webdav_enabled_check", None),
            "backup_interval": getattr(self, "backup_interval_spin", None),
            "webdav_url": getattr(self, "webdav_url_edit", None),
            "webdav_user": getattr(self, "webdav_username_edit", None),
            "restart_timeout": getattr(self, "restart_timeout_spin", None),
            "lock_timeout": getattr(self, "lock_timeout_spin", None),
        }
        self._pending_logo_path: Path | None = None
        self._current_logo_path: Path | None = None

        # Connect signals
        self.cancel_button.clicked.connect(self._cancel)
        self.save_button.clicked.connect(self._save)
        self.restart_button.clicked.connect(self._restart)
        self.close_button.clicked.connect(self.close_signal.emit)
        self.about_repo_button.clicked.connect(
            lambda _checked=False: self._open_external_url("https://github.com/mavinum/CoffeeBot")
        )
        self.about_license_button.clicked.connect(
            lambda _checked=False: self._open_external_url("https://github.com/mavinum/CoffeeBot/blob/master/LICENSE")
        )

        self.select_logo_button.clicked.connect(self._select_logo)

        self.pwd_change_button.clicked.connect(self._change_password)
        self.pwd_show_button.toggled.connect(lambda x: self._toggle_password_visibility(x, self.new_password_edit))
        self.repeat_show_button.toggled.connect(
            lambda x: self._toggle_password_visibility(x, self.password_repeat_edit)
        )

        # WebDAV UI logic
        self.webdav_url_edit.textChanged.connect(self._mark_webdav_modified)
        self.webdav_username_edit.textChanged.connect(self._mark_webdav_modified)
        self.webdav_password_edit.textChanged.connect(self._mark_webdav_modified)
        self.webdav_password_edit.setPlaceholderText("Leave blank to keep; enter new to replace")
        self.webdav_pwd_button.toggled.connect(lambda x: self._toggle_password_visibility(x, self.webdav_password_edit))
        self.webdav_enabled_check.stateChanged.connect(self._mark_webdav_modified)
        self.webdav_enabled_check.stateChanged.connect(self._update_webdav_ui_state)
        self.auto_backup_check.stateChanged.connect(self._mark_webdav_modified)
        self.auto_backup_check.stateChanged.connect(self._update_webdav_ui_state)
        self.backup_interval_spin.valueChanged.connect(self._mark_webdav_modified)
        self.webdav_apply_button.clicked.connect(self._apply_webdav_settings)
        self.webdav_apply_button.setVisible(False)

        # Export logic
        self.export_button.clicked.connect(self._export_data)

        # Autostart UI logic
        self.autostart_check.clicked.connect(self._mark_autostart_modified)
        self.restart_check.clicked.connect(self._mark_autostart_modified)
        self.restart_timeout_spin.valueChanged.connect(self._mark_autostart_modified)
        self.autostart_apply_button.clicked.connect(self._apply_autostart_settings)
        self.autostart_apply_button.setVisible(False)

    @staticmethod
    def _open_external_url(url: str) -> None:
        """Open a URL with the system handler, falling back to Python's browser launcher."""
        if QDesktopServices.openUrl(QUrl(url)):
            return
        if not webbrowser.open(url, new=2):
            logger.error(f"Could not open URL in the default browser: {url}")

    @typing.override
    def showEvent(self, a0) -> None:
        """Trigger logo preview once the widget is actually displayed."""
        super().showEvent(a0)
        if self._current_logo_path:
            self._update_logo_preview(self._current_logo_path)

    # region Core methods
    def set_db(self, db: UserDB) -> None:
        """Set UserDB instance for querying statistics."""
        self._db = db

    def _load_version(self) -> None:
        """Get current app version."""
        version = str(self._config.version)
        self.version_label.setText(version)
        self.about_version_label.setText(f"Version: {version}")

    def load(self) -> None:
        """Load settings into the registered UI fields and display statistics."""
        for key, widget in self._bindings.items():
            if widget is None:
                continue

            # Block signals to prevent triggering 'modified' state during initial load
            widget.blockSignals(True)

            value = self._config.get(key, None)
            # price spinboxes
            if isinstance(widget, QDoubleSpinBox):
                try:
                    if value is None:
                        widget.blockSignals(False)
                        continue
                    widget.setValue(float(value))
                except (TypeError, ValueError):
                    continue
            if isinstance(widget, QSpinBox):
                try:
                    if value is None:
                        widget.blockSignals(False)
                        continue
                    widget.setValue(int(value))
                except (TypeError, ValueError):
                    continue
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QLineEdit):
                if value is None:
                    widget.clear()
                else:
                    widget.setText(str(value))
            # items stored as list -> show as lines in QTextEdit
            elif isinstance(widget, QTextEdit):
                if value is None:
                    widget.clear()
                elif isinstance(value, (list, tuple)):
                    widget.setPlainText("\n".join(str(v) for v in value))
                else:
                    # allow legacy string storage
                    widget.setPlainText(str(value))

            widget.blockSignals(False)

        with QSignalBlocker(self.webdav_password_edit):
            self.webdav_password_edit.clear()

        # Load version
        self._load_version()

        # Load logo
        self._current_logo_path = Path(self._config.get("data_dir")) / Path(self._config.get("logo_file"))

        # Load autostart status
        self.autostart_check.setChecked(self.manager.service_enabled)

        # Load statistics
        self._load_stats()

        # Clear fields
        self.new_password_edit.clear()
        self.password_repeat_edit.clear()
        self.export_status_label.clear()

        # Reset dirty state and visibility
        self.webdav_apply_button.setVisible(False)
        self.autostart_apply_button.setVisible(False)
        self._update_webdav_ui_state()
        self._update_autostart_ui_state()
        self.restart_timeout_spin.setEnabled(self.restart_check.isChecked())

    def _save(self) -> None:
        """Save edited settings to configuration file."""
        vals: dict[str, Any] = {}
        for key, widget in self._bindings.items():
            if widget is None:
                continue

            # Exclude system-level settings that require separate 'Apply' logic
            if key in ("autostart", "auto_restart", "restart_timeout"):
                continue

            if isinstance(widget, QDoubleSpinBox):
                vals[key] = widget.value()
            if isinstance(widget, QSpinBox):
                vals[key] = widget.value()
            elif isinstance(widget, QCheckBox):
                vals[key] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                vals[key] = widget.text()
            elif isinstance(widget, QTextEdit):
                # split lines into a list of non-empty trimmed items
                lines = [ln.strip() for ln in widget.toPlainText().splitlines()]
                vals[key] = [ln for ln in lines if ln]

        if not self._validate_webdav_settings(vals):
            return

        if not self._store_webdav_password():
            return

        # Handle logo update
        if self._pending_logo_path:
            try:
                data_dir = Path(self._config.get("data_dir", ""))
                logo_filename = f"{self._pending_logo_path.name}"
                dest_path = data_dir / logo_filename
                shutil.copy2(self._pending_logo_path, dest_path)
                vals["logo_file"] = logo_filename
                logger.info("Logo updated")
            except Exception as exc:
                logger.error(f"Failed to copy logo file: {exc}")

        self._persist_vals(vals)
        self.save_signal.emit()

    def _persist_vals(self, vals: dict[str, Any]) -> None:
        """Update settings instance and persist to file."""
        if vals:
            self._config.update(vals)
            logger.info("Settings persisted to file")

    def _cancel(self) -> None:
        """Cancel editing settings."""
        self.cancel_signal.emit()

    # end region

    # region Logo settings

    def _select_logo(self) -> None:
        """Open file dialog to select a new logo image."""
        file_filter = "Image files (*.png *.jpg *.jpeg *.bmp *.gif)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo Image", "", file_filter)
        if file_path:
            self._pending_logo_path = Path(file_path)
            self._update_logo_preview(self._pending_logo_path)

    def _update_logo_preview(self, path: Path) -> None:
        """Update the logo preview label with the image."""
        self.logo_file_label.setText(path.name)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            logger.warning("Failed to load logo image")
            self.logo_preview_label.setText("Invalid Image")
            self._pending_logo_path = None
            return

        # Scale pixmap to fit label while preserving aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.logo_preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.logo_preview_label.setPixmap(scaled_pixmap)
        self.logo_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_file_label.setText(path.name)

    # end region

    # region Export Logic

    def _select_export_file(self) -> Path | None:
        """Open file dialog to select export location."""
        file_filter = "CSV files (*.csv)" if self.csv_select.isChecked() else "Excel files (*.xlsx)"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Export File", "", file_filter)
        if file_path:
            self.export_status_label.setText(f"Save to: {file_path}")
            return Path(file_path)
        self.export_status_label.setText("")
        return None

    def _export_data(self) -> None:
        """Export user data to CSV or XLSX, either locally or via WebDAV."""
        is_csv = self.csv_select.isChecked()
        is_xlsx = self.xlsx_select.isChecked()
        is_webdav = self.webdav_select.isChecked()
        is_file = self.file_select.isChecked()

        if self._db is None:
            logger.error("No DB available for export")
            self.export_status_label.setText("Error: No database connected")
            return

        # Get data from database
        try:
            data = self._db.get_users_for_export()
            if not data:
                self.export_status_label.setText("No data to export")
                return
        except Exception as exc:
            logger.error(f"Database error during export: {exc}")
            self.export_status_label.setText("DB Error fetching data")
            return

        if is_csv:
            ext = ".csv"
            save_method = self._write_csv
        elif is_xlsx:
            ext = ".xlsx"
            save_method = self._write_xlsx

        if is_file:
            file_path = self._select_export_file()
            if file_path is None:
                self.export_status_label.setText("Please select a save location first")
                return

            file_path = file_path.with_suffix(ext)
            self.export_status_label.setText(f"Saved to {file_path.name}")
            success: bool = save_method(data, file_path)

            if not success:
                self.export_status_label.setText("Error during saving file.")
            else:
                self.export_status_label.setText("Exported successfully!")

            self.webdav_select.setChecked(True)

        elif is_webdav:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                file_path = Path(tmp.name)
            success: bool = save_method(data, file_path)

            if not success:
                self.export_status_label.setText("Error during saving file.")
            else:
                self.export_status_label.setText("File generated successfully!")

            self.webdav_export.emit(str(file_path))
            self.export_status_label.setText("Upload requested...")

    def _write_csv(self, data: list[tuple], path: Path) -> bool:
        """Write user data to CSV file. Returns success."""
        try:
            headers = ["ID", "Forename", "Surename", "Group", "Email", "Balance"]
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False
        else:
            return True

    def _write_xlsx(self, data: list[tuple], path: Path) -> bool:
        """Write user data to XLSX file using openpyxl. Returns success."""
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Users"
            headers = ["ID", "Forename", "Surename", "Group", "Email", "Balance"]
            ws.append(headers)
            for row in data:
                ws.append(row)
            wb.save(str(path))
        except Exception as e:
            logger.error(f"XLSX export failed: {e}")
            return False
        else:
            return True

    # end region

    # region Password settings

    def _toggle_password_visibility(self, checked: bool, field: QLineEdit) -> None:
        """Toggle character visibility of password field."""
        field.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _change_password(self) -> None:
        """Change master password and save to settings."""
        new_pw = self.new_password_edit.text()
        repeat_pw = self.password_repeat_edit.text()
        if not new_pw or not repeat_pw:
            self.pwd_status_label.setText("Password fields cannot be empty")
            return
        if new_pw != repeat_pw:
            self.pwd_status_label.setText("Passwords do not match")
            return
        try:
            set_master_password(new_pw)
            self.pwd_status_label.setText("Password updated successfully")
            self.new_password_edit.clear()
            self.password_repeat_edit.clear()
        except Exception as exc:
            logger.error(f"Failed to set master password: {exc}")
            self.pwd_status_label.setText("Failed to update password")

    # end region

    # region Statistics

    def _load_stats(self) -> None:
        """Load and display consumption statistics from database."""
        if self._db is None:
            logger.warning("No DB available for stats")
            return

        try:
            repo = StatsRepo(self._db)
            summary = repo.get_consumption_stats()

            # Map category keys to UI elements
            category_map = {
                "cat_1": {
                    "group": self.cat_1_group,
                    "week_label": self.cat_1_week_label,
                    "month_label": self.cat_1_month_label,
                    "total_label": self.cat_1_total_label,
                },
                "cat_2": {
                    "group": self.cat_2_group,
                    "week_label": self.cat_2_week_label,
                    "month_label": self.cat_2_month_label,
                    "total_label": self.cat_2_total_label,
                },
                "cat_3": {
                    "group": self.cat_3_group,
                    "week_label": self.cat_3_week_label,
                    "month_label": self.cat_3_month_label,
                    "total_label": self.cat_3_total_label,
                },
            }

            # Fill category cards
            for cat_key, elements in category_map.items():
                group_box = elements["group"]
                if group_box is None:
                    continue

                # Set group box title from category items
                items = self._config.get(f"{cat_key}_items", [])
                title = " - ".join(str(i) for i in items) if isinstance(items, (list, tuple)) and items else cat_key
                group_box.setTitle(title)

                # Set count labels
                if cat_key in summary.by_category:
                    counts = summary.by_category[cat_key]
                    for label_key, label_name in [
                        ("week_label", "week"),
                        ("month_label", "month"),
                        ("total_label", "total"),
                    ]:
                        label_widget = elements[label_key]
                        if label_widget is not None:
                            label_widget.setText(str(getattr(counts, label_name)))
                else:
                    # No data for this category yet
                    for label_key in ["week_label", "month_label", "total_label"]:
                        label_widget = elements[label_key]
                        if label_widget is not None:
                            label_widget.setText("0")

            # Fill overall totals
            self.overall_week_label.setText(str(summary.week))
            self.overall_month_label.setText(str(summary.month))
            self.overall_total_label.setText(str(summary.total))

        except Exception as e:
            logger.error(f"Failed to load statistics: {e}")

        # endregion

        # region Autostart

    def _mark_autostart_modified(self) -> None:
        """Mark autostart settings as changed and show Apply button."""
        self.autostart_apply_button.setVisible(True)
        if self.restart_check.isChecked() != self._config.get("auto_restart"):
            self.autostart_apply_button.setText("Apply and Restart")
        else:
            self.autostart_apply_button.setText("Apply")
        self._update_autostart_ui_state()

    def _update_autostart_ui_state(self) -> None:
        """Set enabled/disabled states for autostart controls."""
        autostart_enabled = self.autostart_check.isChecked()
        auto_restart = self.restart_check.isChecked()

        self.restart_check.setEnabled(autostart_enabled)
        self.restart_timeout_spin.setEnabled(autostart_enabled and auto_restart)

    def _apply_autostart_settings(self) -> None:
        """Persist and apply systemd service settings."""
        restart_required = False
        # Collect current UI state
        autostart_enabled = self.autostart_check.isChecked()
        auto_restart = self.restart_check.isChecked()
        restart_timeout = self.restart_timeout_spin.value()

        # Get persisted state to detect what actually changed
        old_restart = self._config.get("auto_restart")
        old_timeout = self._config.get("restart_timeout")

        vals = {"autostart": autostart_enabled, "auto_restart": auto_restart, "restart_timeout": restart_timeout}

        try:
            if not self.manager.service_exists:
                logger.debug("Systemd service not existant")
                if autostart_enabled:
                    logger.debug("Autostart enabled")
                    success, msg = self.manager.install()
                    restart_required = True
                else:
                    logger.debug("Autostart not enabled")
                    success = True
                    msg = "Autostart was never enabled."

            elif autostart_enabled:
                logger.debug("Check 1: Systemd service exists autostart enabled")
                success, msg = self.manager.enable()
                restart_required = True
            else:
                logger.debug("Systemd service exists autostart disabled")
                success, msg = self.manager.disable()

            if auto_restart != old_restart or restart_timeout != old_timeout:
                logger.debug("Check 3: auto-restart changed")
                success, msg = self.manager.update_overrides(auto_restart, int(restart_timeout))
                if self.manager.service_exists:
                    logger.debug("Restart settings changed and service exists: restart required")
                    restart_required = True

            logger.info(f"Systemd apply result: {success} - {msg}")
            if success:
                self.system_status_label.setText(msg)
            else:
                self.system_status_label.setText(f"Error: {msg}")
                return

        except Exception as exc:
            error_msg = f"System Error: {exc!s}"
            self.system_status_label.setText(error_msg)
            logger.error(error_msg)
            return

        self._persist_vals(vals)
        self.autostart_apply_button.setVisible(False)
        if restart_required:
            self._restart()

    def _restart(self) -> None:
        """Restart app process or systemd service."""
        self.system_label.setText("Restarting....")
        if "INVOCATION_ID" in os.environ and self.manager.service_running:
            logger.info("Restarting systemd service....")
            self.manager.restart()
        elif self.manager.service_enabled:
            logger.info("Closing process and starting systemd service....")
            # TODO @Mavinum: Future restart control should restart the service or launch the app.
            success, msg = self.manager.restart()
            if not success:
                self.system_status_label.setText(f"Error: {msg}")
                logger.error(f"Systemd restart failed: {msg}")
                return
            time.sleep(0.2)
            self.close_signal.emit()
        else:
            logger.info("Restarting process....")
            self.restart_signal.emit()

    # endregion

    # region WebDAV UI Logic

    def _mark_webdav_modified(self) -> None:
        """Mark WebDAV settings as changed and show Apply button."""
        self.webdav_apply_button.setVisible(True)
        self._update_webdav_ui_state()

    def _update_webdav_ui_state(self) -> None:
        """Enable/Disable WebDAV controls based on the 'enabled' flag."""
        webdav_enabled = self.webdav_enabled_check.isChecked()
        auto_backup_enabled = self.auto_backup_check.isChecked()

        # Auto-backup and manual backup buttons only work if WebDAV is enabled
        self.auto_backup_check.setEnabled(webdav_enabled)
        self.backup_button.setEnabled(webdav_enabled)

        # Interval only works if BOTH webdav is enabled AND auto-backup is checked
        self.backup_interval_spin.setEnabled(webdav_enabled and auto_backup_enabled)

    def _collect_webdav_settings(self) -> dict[str, Any]:
        """Read the WebDAV controls into configuration values."""
        return {
            "webdav_enabled": self.webdav_enabled_check.isChecked(),
            "auto_backup_enabled": self.auto_backup_check.isChecked(),
            "backup_interval": self.backup_interval_spin.value(),
            "webdav_url": self.webdav_url_edit.text().strip(),
            "webdav_user": self.webdav_username_edit.text().strip(),
        }

    def _validate_webdav_settings(self, values: dict[str, Any]) -> bool:
        """Validate WebDAV settings before they are persisted or applied."""
        if not values.get("webdav_enabled", False):
            values["auto_backup_enabled"] = False
            return True

        url = str(values.get("webdav_url", "")).strip()
        if not url:
            self.webdav_status_label.setText("WebDAV URL is required")
            logger.warning("WebDAV settings rejected: URL is missing")
            return False

        interval = int(str(values.get("backup_interval", 0)).strip())
        if interval <= 0:
            self.webdav_status_label.setText("Interval must be positive!")
            logger.warning("WebDAV settings rejected: backup interval is invalid")
            return False

        values["backup_interval"] = interval
        credential = self.webdav_password_edit.text()
        if not credential:
            try:
                credential = get_webdav_credential()
            except CredentialStoreError as exc:
                self.webdav_status_label.setText(str(exc))
                logger.error(f"Could not validate WebDAV credential: {exc}")
                return False

        if not credential:
            self.webdav_status_label.setText("App password or token required")
            logger.warning("WebDAV settings rejected: credential is missing")
            return False

        return True

    def _store_webdav_password(self) -> bool:
        """Store a newly entered WebDAV credential without persisting it in settings."""
        credential = self.webdav_password_edit.text()
        if not credential:
            return True

        try:
            store_webdav_credential(credential)
        except CredentialStoreError as exc:
            self.webdav_status_label.setText(str(exc))
            logger.error(f"Could not store WebDAV credential: {exc}")
            return False

        with QSignalBlocker(self.webdav_password_edit):
            self.webdav_password_edit.clear()
        self.webdav_status_label.setText("Credential saved to OS keyring.")
        return True

    def _apply_webdav_settings(self) -> None:
        """Persist and apply only the WebDAV settings."""
        values = self._collect_webdav_settings()
        if not self._validate_webdav_settings(values):
            return

        if not self._store_webdav_password():
            return

        self._persist_vals(values)
        self.webdav_apply_button.setVisible(False)
        self.webdav_settings_applied.emit()

    # endregion
