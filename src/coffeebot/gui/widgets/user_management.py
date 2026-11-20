"""
################################################################################

Custom PyQt user interfaces for user data manipulation in the main GUI.

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

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6 import uic
from PyQt6.QtCore import QDir, pyqtSignal
from PyQt6.QtWidgets import QWidget

from coffeebot.db.users import CreateUser

if TYPE_CHECKING:
    from coffeebot.db.users import User, UserDB

from .custom_widgets import EmailValidator

basedir = Path(__file__).parent
style_path = basedir / "widget_styles.qss"
QDir.addSearchPath("coffeebot-icons", str(basedir.parent / "icons"))

AddUserWidgetUI, _ = uic.loadUiType(basedir / "user_widget.ui")
EditUserWidgetUI, _ = uic.loadUiType(basedir / "edit_user_widget.ui")

with style_path.open("r", encoding="utf-8") as style_file:
    WIDGET_STYLE = style_file.read()


class AddUserWidget(QWidget, AddUserWidgetUI):
    """Widget to add data to create a new user."""

    cancel_signal = pyqtSignal()  # ty: ignore[missing-argument]
    save_signal = pyqtSignal()  # ty: ignore[missing-argument]

    def __init__(self, parent=None, db: UserDB | None = None):
        super().__init__(parent)  # ty: ignore[invalid-argument-type]
        self.user_db: UserDB | None = db
        self.setupUi(self)
        self.setStyleSheet(WIDGET_STYLE)
        self.email_label.setValidator(EmailValidator())

        self.cancel_button.clicked.connect(self._cancel)
        self.add_user_button.clicked.connect(self._add_user)

    def _clear(self) -> None:
        """Clear all input filds in the widget."""
        self.forename_label.clear()
        self.surename_label.clear()
        self.email_label.clear()
        self.group_label.clear()
        self.telegram_label.clear()
        self.balance_label.clear()
        self.consent_check.setChecked(False)

    def _cancel(self) -> None:
        """Cancel new user registration and return to home screen."""
        self._clear()
        self.cancel_signal.emit()

    def _add_user(self) -> None:
        """Save new user data to database and return to home screen."""
        user = CreateUser(
            self.forename_label.text(),
            self.surename_label.text(),
            self.group_label.text(),
            self.email_label.text(),
            self.telegram_label.text(),
            balance=self.balance_label.text(),
        )

        self.user_db.add(user)
        self.save_signal.emit()
        self._clear()


class EditUserWidget(QWidget, EditUserWidgetUI):
    """Widget to change data of existing user."""

    cancel_signal = pyqtSignal()  # ty: ignore[missing-argument]
    delete_signal = pyqtSignal()  # ty: ignore[missing-argument]
    save_signal = pyqtSignal()  # ty: ignore[missing-argument]

    def __init__(self, parent=None, db: UserDB | None = None):
        super().__init__(parent)  # ty: ignore[invalid-argument-type]
        self.user_db = db
        self.user: User | None = None
        self.setupUi(self)
        self.setStyleSheet(WIDGET_STYLE)

        self.cancel_button.clicked.connect(self._cancel_edit)
        self.delete_button.clicked.connect(self._delete_user)
        self.save_button.clicked.connect(self._save_user)

        self.deposit_1_button.clicked.connect(lambda: self._add_deposit(1))
        self.deposit_5_button.clicked.connect(lambda: self._add_deposit(5))
        self.deposit_10_button.clicked.connect(lambda: self._add_deposit(10))
        self.deposit_50_button.clicked.connect(lambda: self._add_deposit(50))
        self.custom_deposit_button.clicked.connect(lambda: self._add_deposit(self.custom_deposit_label.value()))

    def set_user(self, user: User | None) -> None:
        """Display current data of specified user."""
        if user is None:
            return
        self.user = user
        self.forename_label.setText(user.forename)
        self.surename_label.setText(user.surename)
        self.group_label.setText(user.workgroup)
        self.email_label.setText(user.email)
        self.telegram_label.setText("" if user.telegram_id is None else str(user.telegram_id))
        self.balance_label.setText(f"{user.balance:.2f}")

    def _save_user(self) -> None:
        """Emit save signal with current user data as UserDict."""
        self.user.forename = self.forename_label.text()
        self.user.surename = self.surename_label.text()
        self.user.workgroup = self.group_label.text()
        self.user.email = self.email_label.text()
        telegram_id = self.telegram_label.text().strip()
        self.user.telegram_id = int(telegram_id) if telegram_id else None
        self.user.balance = None

        self.user_db.update(self.user)
        self.save_signal.emit()
        self._clear()

    def _delete_user(self) -> None:
        """Emit delete signal with current user data as UserDict."""
        self.user.forename = self.forename_label.text()
        self.user.surename = self.surename_label.text()
        self.user.workgroup = self.group_label.text()
        self.user.email = self.email_label.text()
        telegram_id = self.telegram_label.text().strip()
        self.user.telegram_id = int(telegram_id) if telegram_id else None
        self.user.balance = float(self.balance_label.text())

        self.delete_signal.emit()
        self._clear()

    def _cancel_edit(self) -> None:
        """Cancel editing user data and clear fields."""
        self._clear()
        self.cancel_signal.emit()

    def _clear(self) -> None:
        """Clear all albels and edits and remove self.user."""
        self.forename_label.clear()
        self.surename_label.clear()
        self.group_label.clear()
        self.email_label.clear()
        self.telegram_label.clear()
        self.balance_label.clear()
        self.user = None

    def _add_deposit(self, amount: float) -> None:
        """Deposit given amount to current balance."""
        user_id = self.user.user_id
        if self.user_db is not None:
            self.user_db.transfer(user_id, amount)
        self.user = self.user_db.get_user(user_id)
        self.balance_label.setText(f"{self.user.balance:.2f}")
