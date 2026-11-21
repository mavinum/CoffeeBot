# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only

import bcrypt
import pytest

from coffeebot.auth import verify_password
from coffeebot.config.settings import Settings
from coffeebot.gui.widgets.custom_widgets import AuthenticationWidget


def test_password_check_accepts_correct_password_and_rejects_wrong_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify passwords using the stored bcrypt hash."""
    password_hash = bcrypt.hashpw(b"secret", bcrypt.gensalt(rounds=4)).decode("utf-8")

    class DummySettings:
        def get(self, key, default=None):
            return password_hash if key == "master_pwd_hash" else default

    monkeypatch.setattr("coffeebot.auth.Settings.get_instance", DummySettings)

    assert verify_password("secret") is True
    assert verify_password("wrong") is False


@pytest.mark.usefixtures("qapp")
def test_authentication_widget_sets_password_when_hash_is_missing(tmp_path) -> None:
    """Set a confirmed password on first access to a restricted area."""
    settings = Settings.configure_app(
        "CoffeeBot",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=tmp_path / "default.json",
    )
    widget = AuthenticationWidget()
    confirmed: list[str] = []
    widget.confirm_signal.connect(confirmed.append)

    assert not widget.confirm_password_edit.isHidden()
    widget.password_edit.setText("new-secret")
    widget.confirm_password_edit.setText("new-secret")
    widget.confirm_button.click()

    assert settings.get("master_pwd_hash")
    assert verify_password("new-secret")
    assert confirmed == ["new-secret"]
    assert widget.confirm_password_edit.isHidden()


@pytest.mark.parametrize(
    ("password", "confirmation", "expected_status"),
    [
        ("", "", "Password cannot be empty"),
        ("new-secret", "different", "Passwords do not match"),
    ],
)
@pytest.mark.usefixtures("qapp")
def test_authentication_widget_rejects_invalid_password_setup(
    tmp_path, password: str, confirmation: str, expected_status: str
) -> None:
    """Do not save or accept an empty or unconfirmed first-run password."""
    settings = Settings.configure_app(
        "CoffeeBot",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=tmp_path / "default.json",
    )
    widget = AuthenticationWidget()
    confirmed: list[str] = []
    widget.confirm_signal.connect(confirmed.append)
    widget.password_edit.setText(password)
    widget.confirm_password_edit.setText(confirmation)

    widget.confirm_button.click()

    assert settings.get("master_pwd_hash") is None
    assert widget.status_label.text() == expected_status
    assert confirmed == []


@pytest.mark.usefixtures("qapp")
def test_authentication_widget_hides_confirmation_for_existing_hash(tmp_path) -> None:
    """Keep the one-field password prompt for already configured installations."""
    settings = Settings.configure_app(
        "CoffeeBot",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=tmp_path / "default.json",
    )
    settings.set("master_pwd_hash", bcrypt.hashpw(b"existing-secret", bcrypt.gensalt(rounds=4)).decode("utf-8"))
    widget = AuthenticationWidget()
    confirmed: list[str] = []
    widget.confirm_signal.connect(confirmed.append)
    widget.password_edit.setText("existing-secret")

    widget.confirm_button.click()

    assert widget.confirm_password_edit.isHidden()
    assert confirmed == ["existing-secret"]
