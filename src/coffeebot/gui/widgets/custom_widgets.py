"""
#############################################################################

Custom low-level PyQt Widgets for handling inputs or displaying data.

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

import typing
from pathlib import Path

from pyisemail import is_email
from PyQt6 import uic
from PyQt6.QtCore import QDir, Qt, pyqtSignal
from PyQt6.QtGui import QValidator
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QPushButton, QTableWidgetItem, QWidget

from coffeebot.auth import verify_password
from coffeebot.config.settings import Settings

basedir = Path(__file__).parent
style_path = basedir / "widget_styles.qss"
QDir.addSearchPath("coffeebot-icons", str(basedir.parent / "icons"))

AuthenticationWidgetUI, _ = uic.loadUiType(basedir / "login_widget.ui")
ResetChallengeWidgetUI, _ = uic.loadUiType(basedir / "reset_challenge_widget.ui")
EditInfoWidgetUI, _ = uic.loadUiType(basedir / "edit_info_widget.ui")

with style_path.open("r", encoding="utf-8") as style_file:
    WIDGET_STYLE = style_file.read()


class PriceItem(QTableWidgetItem):
    """QTableWidgetItem for storing ans sorting price numbers including euro sign."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setTextAlignment(Qt.AlignmentFlag.AlignVCenter + Qt.AlignmentFlag.AlignRight)

    def __lt__(self, other: QTableWidgetItem):
        val = self.text().strip(" \u20ac")
        other_val = other.text().strip(" \u20ac")
        try:
            return float(val) < float(other_val)
        except ValueError:
            return super().__lt__(other)


class PriceButton(QPushButton):
    """Round button with price and description label below."""


class EmailValidator(QValidator):
    """Validate the string syntax of an email input field."""

    def validate(self, input_str: str, pos: int) -> tuple[QValidator.State, str, int]:  # ty:ignore[invalid-method-override]
        """Reimplement to validate email format."""
        if " " in input_str:
            return (QValidator.State.Invalid, input_str, pos)
        if is_email(input_str):
            return (QValidator.State.Acceptable, input_str, pos)
        return (QValidator.State.Intermediate, input_str, pos)

    def fixup(self, input_str: str) -> str:  # ty:ignore[invalid-method-override]
        """Reimplement to remove whitespaces."""
        return input_str.strip()


class EmailLineEdit(QLineEdit):
    """LineEdit for typing email addresses with validation."""


class PasswordDialog(QInputDialog):
    """Dialog to input password for authentication."""

    def __init__(self, parent=None):
        super().__init__(parent)


class AuthenticationWidget(QWidget, AuthenticationWidgetUI):
    """Widget with password prompt for user authentication."""

    cancel_signal = pyqtSignal()
    confirm_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = Settings.get_instance()
        self.setupUi(self)
        self.setStyleSheet(WIDGET_STYLE)
        self._invalid = False

        self.cancel_button.clicked.connect(self._cancel)
        self.confirm_button.clicked.connect(self._authenticate)
        self.password_edit.returnPressed.connect(self._authenticate)
        self.show_pwd_button.toggled.connect(self._toggle_pwd_visibility)

    def _clear(self) -> None:
        """Clear all input filds in the widget."""
        self.password_edit.clear()
        self.status_label.clear()

        if self._invalid:
            self.password_edit.setStyleSheet("background-color: rgb(200, 183, 183);")
            self._invalid = False

    def _authenticate(self) -> None:
        """Check password and send confirm signal, if correct."""
        text = self.password_edit.text()
        if verify_password(text):
            self._clear()
            self.confirm_signal.emit(text)
            return
        self._invalid = True
        self.status_label.setText("Invalid password")
        self.password_edit.selectAll()
        self.password_edit.setStyleSheet("background-color: rgb(182, 82, 93);")

    @typing.override
    def _toggle_pwd_visibility(self, checked: bool) -> None:
        """Toggle character visibility of password edit."""
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _cancel(self) -> None:
        """Cancel new user registration and return to home screen."""
        self._clear()
        self.cancel_signal.emit()


class ResetChallengeWidget(QWidget, ResetChallengeWidgetUI):
    """Widget to edit or reset challenge settings."""

    cancel_signal = pyqtSignal()
    confirm_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setStyleSheet(WIDGET_STYLE)
        self._config = Settings.get_instance()

        self.cancel_button.clicked.connect(self._cancel)
        self.save_button.clicked.connect(self._save)
        self.delete_button.clicked.connect(self._delete_reward)

    def load(self) -> None:
        """Load config to ui elements."""
        self.challenge_goal_edit.setText(str(self._config["challenge_goal"]))
        self.challenge_current_edit.setText(str(self._config["challenge_current"]))
        for item in self._config["challenge_rewards"]:
            self.reward_box.addItem(item)

        selected_reward = self._config["selected_reward"]
        if selected_reward not in self._config["challenge_rewards"]:
            self.reward_box.addItem(selected_reward)
        self.reward_box.setCurrentText(selected_reward)
        self.cat_1_select.setChecked(self._config["tracked_categories"]["cat_1"])
        self.cat_2_select.setChecked(self._config["tracked_categories"]["cat_2"])
        self.cat_3_select.setChecked(self._config["tracked_categories"]["cat_3"])

    def _clear(self) -> None:
        """Clear values form widgets."""
        self.challenge_goal_edit.clear()
        self.challenge_current_edit.clear()
        self.reward_box.clear()
        self.cat_1_select.setChecked(False)
        self.cat_2_select.setChecked(False)
        self.cat_3_select.setChecked(False)

    def _save(self) -> None:
        """Save the current changes and emit confirmation signal."""
        selected_reward = self.reward_box.currentText().strip()
        rewards = list(self._config["challenge_rewards"])
        if selected_reward and selected_reward not in rewards:
            rewards.append(selected_reward)

        vals = {
            "challenge_goal": int(self.challenge_goal_edit.text()),
            "challenge_current": int(self.challenge_current_edit.text()),
            "selected_reward": selected_reward,
            "challenge_rewards": rewards,
            "tracked_categories": {
                "cat_1": self.cat_1_select.isChecked(),
                "cat_2": self.cat_2_select.isChecked(),
                "cat_3": self.cat_3_select.isChecked(),
            },
        }

        self._config.update(vals)
        self._clear()
        self.confirm_signal.emit()

    def _delete_reward(self) -> None:
        """Remove the currently displayed reward from the available rewards list."""
        current_reward = self.reward_box.currentText().strip()
        if not current_reward:
            return

        rewards = [reward for reward in self._config["challenge_rewards"] if reward != current_reward]
        if current_reward == self._config["selected_reward"]:
            selected_reward = rewards[0] if rewards else ""
        else:
            selected_reward = self._config["selected_reward"]

        vals = {"challenge_rewards": rewards, "selected_reward": selected_reward}
        self._config.update(vals)

        self.reward_box.clear()
        for reward in rewards:
            self.reward_box.addItem(reward)
        if selected_reward and selected_reward in rewards:
            self.reward_box.setCurrentText(selected_reward)
        elif rewards:
            self.reward_box.setCurrentIndex(0)

    def _cancel(self) -> None:
        """Cancel new user registration and return to home screen."""
        self._clear()
        self.cancel_signal.emit()


class EditInfoWidget(QWidget, EditInfoWidgetUI):
    """Widget to edit the text the main pages info fields."""

    cancel_signal = pyqtSignal()
    confirm_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setStyleSheet(WIDGET_STYLE)
        self._config = Settings.get_instance()

        self.cancel_button.clicked.connect(self._cancel)
        self.save_button.clicked.connect(self._save)

    def load(self) -> None:
        """Update gui elements on enter, e.g. when page in stacked widget is changed."""
        text = self._config["info_text"]
        self.info_text_browser.setPlainText(text)

    def _save(self) -> None:
        """Save the current changes and emit confirmation signal."""
        text = self.info_text_browser.toPlainText()
        self._config.set("info_text", text)
        self.confirm_signal.emit()

    def _cancel(self) -> None:
        """Cancel new user registration and return to home screen."""
        self.cancel_signal.emit()
