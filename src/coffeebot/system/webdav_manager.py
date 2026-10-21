"""
################################################################################

WebDAV backup manager for CoffeeBot.

This module provides the `WebDavManager` class which handles the synchronization
of application data (database and logs) to a Nextcloud/WebDAV server.
It uses a QThread Worker pattern for network operations and a QTimer for
scheduled backups.

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

import contextlib
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from loguru import logger
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from webdav4.client import Client

from coffeebot.config.settings import Settings


class Action(Enum):
    """WebDav action for upload."""

    EXPORT = auto()
    BACKUP = auto()


class WebDavWorker(QObject):
    """Worker class that handles the actual WebDAV network operations."""

    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    export_finished = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self._config = Settings.get_instance()

    def _get_client(self) -> Client | None:
        """Create and return WebDAV client based on current settings."""
        webdav_url = str(self._config.get("webdav_url", "")).rstrip("/") + "/"
        user = str(self._config.get("webdav_user"))
        pwd = str(self._config.get("webdav_password"))
        try:
            # Bearer Token (if user is empty)
            if not user and pwd:
                return Client(base_url=webdav_url, headers={"Authorization": f"Bearer {pwd}"})

            # User and password (or at best app password in Nextcloud)
            return Client(base_url=webdav_url, auth=(user, pwd))

        except Exception as exc:
            logger.error(f"Failed to initialize WebDAV client: {exc}")
            return None

    @staticmethod
    def _quit_current_thread() -> None:
        """Request shutdown of the thread executing this worker."""
        thread = QThread.currentThread()
        if thread is not None:
            thread.quit()

    def upload_export(self, local_path: Path) -> None:
        """Upload an exported file to the 'exports' folder on WebDAV."""
        client = self._get_client()
        if not client:
            self.export_finished.emit(False, "WebDAV client could not be initialized.")
            return

        try:
            with contextlib.suppress(Exception):
                client.mkdir("exports")

            filename = Path(local_path).name
            ext = Path(local_path).suffix
            timestamp = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M")
            remote_path = f"exports/data_export_{timestamp}{ext}"

            if client.exists(remote_path):
                client.remove(remote_path)

            client.upload_file(local_path, remote_path)
            self.export_finished.emit(True, f"Export {filename} uploaded successfully.")

        except Exception as exc:
            logger.error(f"WebDAV export upload failed: {exc}")
            self.export_finished.emit(False, f"Upload failed: {exc}")

    def run_backup(self) -> None:
        """Perform backup process and emits signals for progress and completion."""
        client = self._get_client()
        if not client:
            self.finished.emit(False, "WebDAV client could not be initialized. Check settings.")
            return

        try:
            db_path = Path(str(self._config.get("data_dir"))) / Path(str(self._config.get("db_file")))
            logs_dir = Path(str(self._config.get("log_dir")))
            config_path = self._config.path

            # Create necessary subfolders if they don't exist
            for folder in ["db", "logs"]:
                with contextlib.suppress(Exception):
                    client.mkdir(folder)

            # Backup database
            if db_path.exists():
                self.progress.emit("Uploading database...")
                timestamp = datetime.now().strftime("%Y-%m")
                remote_db_name = f"coffee_users_{timestamp}.db"
                remote_db_path = f"db/{remote_db_name}"
                if client.exists(remote_db_path):
                    client.remove(remote_db_path)
                client.upload_file(db_path, remote_db_path)

            # Backup logs
            if logs_dir.exists() and logs_dir.is_dir():
                self.progress.emit("Uploading logs...")
                for log_file in logs_dir.glob("*.log"):
                    remote_path = f"logs/{log_file.name}"
                    if client.exists(remote_path):
                        client.remove(remote_path)
                    client.upload_file(log_file, remote_path)

            # Backup settings
            if config_path.exists():
                self.progress.emit("Uploading settings...")
                remote_path = config_path.name
                if client.exists(remote_path):
                    client.remove(remote_path)
                client.upload_file(config_path, remote_path)

            self.finished.emit(True, "Backup completed successfully.")

        except Exception as exc:
            logger.error(f"Backup failed: {exc}")
            self.finished.emit(False, f"Backup failed: {exc}")

    def check_connection(self) -> None:
        """Validate the configured credentials with a harmless WebDAV request."""
        client = self._get_client()
        if client is None:
            self.progress.emit("WebDAV connection failed")
            self._quit_current_thread()
            return

        try:
            # Try to list the root directory to verify credentials
            client.ls("/")
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {401, 403}:
                message = "Credentials rejected"
            elif status_code == 404:
                message = "Remote root directory not accessible"
            else:
                message = "Server unavailable"
            logger.warning(f"{message} ({type(exc).__name__})")
            self.progress.emit(message)
            self._quit_current_thread()
            return

        self.progress.emit("WebDAV valid!")
        self._quit_current_thread()


class WebDavManager(QObject):
    """Manager class that handles WebDAV backups and scheduling."""

    backup_finished = pyqtSignal(bool, str)
    backup_progress = pyqtSignal(str)
    export_finished = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self._settings = Settings.get_instance()
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self.perform_upload)
        self._thread: QThread | None = None
        self._worker: WebDavWorker | None = None

    def perform_upload(self, action: Action, file: Path | None = None) -> None:
        """Start the backup process in a separate QThread."""
        if self._thread is not None:
            # Check if the C++ object still exists before calling isRunning
            try:
                if self._thread.isRunning():
                    self.backup_progress.emit("Upload in progress - try later.")
                    logger.warning("WebDAV upload request ignored: Upload already in progress")
                    return
            except RuntimeError:
                self._thread = None

        self._thread = QThread(self)
        self._worker = WebDavWorker()
        self._worker.moveToThread(self._thread)

        if action == Action.BACKUP:
            self._thread.started.connect(self._worker.run_backup)
        elif action == Action.EXPORT and file is not None:
            self._thread.started.connect(lambda: self._worker.upload_export(file))  # ty: ignore[unresolved-attribute]
            self._worker.export_finished.connect(self.export_finished.emit)
        self._worker.progress.connect(self.backup_progress.emit)
        self._worker.finished.connect(self.backup_finished.emit)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._handle_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _handle_thread_finished(self) -> None:
        """Reset thread reference when it finishes."""
        self._thread = None

    def check_connection(self) -> None:
        """Check WebDAV credentials in a separate thread."""
        if self._thread is not None:
            try:
                if self._thread.isRunning():
                    self.backup_progress.emit("Already in progress")
                    logger.warning("WebDAV connection check ignored: operation already in progress")
                    return
            except RuntimeError:
                self._thread = None

        self._thread = QThread(self)
        self._worker = WebDavWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.check_connection)
        self._worker.progress.connect(self.backup_progress.emit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._handle_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def start_auto_backup(self, interval_hours: int = 24) -> None:
        """Schedule automated backups."""
        if interval_hours <= 0:
            self.backup_progress.emit("Backup interval must be positive")
            return
        interval_ms = interval_hours * 3600 * 1000
        self._timer.stop()
        self._timer.start(interval_ms)

    def stop_auto_backup(self) -> None:
        """Stop the scheduled backups."""
        if self._timer.isActive():
            self._timer.stop()
            logger.info("Auto-backup schedule stopped.")

    def stop(self) -> None:
        """Stop all dependent threads and timers."""
        self.stop_auto_backup()
        if self._thread is None or not self._thread.isRunning():
            return

        self._thread.quit()
        if self._thread.wait(5000):
            return

        logger.warning("WebDAV worker did not stop gracefully; terminating thread")
        self._thread.terminate()
        self._thread.wait()
