from __future__ import annotations

import pytest

from coffeebot.db.users import User
from coffeebot.gui.widgets.user_management import EditUserWidget

pytestmark = pytest.mark.usefixtures("qapp")


class _DummyUserDB:
    """Capture updates made by the user editor."""

    def __init__(self) -> None:
        self.updated_user: User | None = None

    def update(self, user: User) -> None:
        """Record the updated user."""
        self.updated_user = user


@pytest.mark.parametrize(("telegram_id", "expected"), [("", None), ("  ", None), ("12345", 12345)])
def test_save_user_accepts_optional_telegram_id(telegram_id: str, expected: int | None) -> None:
    """Save an empty Telegram ID as None and preserve numeric IDs."""
    database = _DummyUserDB()
    widget = EditUserWidget(db=database)
    user = User(1, "First", "Last", "Group", "test@example.com", None, 10.0)
    widget.set_user(user)
    assert widget.telegram_label.text() == ""
    widget.telegram_label.setText(telegram_id)

    widget.save_button.click()

    assert database.updated_user is user
    assert user.telegram_id == expected


@pytest.mark.parametrize(("telegram_id", "expected"), [("", None), ("  ", None), ("12345", 12345)])
def test_delete_user_accepts_optional_telegram_id(telegram_id: str, expected: int | None) -> None:
    """Delete with an empty Telegram ID without attempting int("")."""
    widget = EditUserWidget()
    user = User(1, "First", "Last", "Group", "test@example.com", None, 10.0)
    widget.set_user(user)
    widget.telegram_label.setText(telegram_id)

    widget.delete_button.click()

    assert user.telegram_id == expected
