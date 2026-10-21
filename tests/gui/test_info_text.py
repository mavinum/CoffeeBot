from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from coffeebot.gui.main_window import CoffeeBot
from coffeebot.gui.widgets import custom_widgets

pytestmark = pytest.mark.usefixtures("qapp")


class _DummyConfig:
    """Minimal settings double for the info-text widgets."""

    def __init__(self, values: dict[str, Any]):
        self.values = values

    def __getitem__(self, key: str) -> Any:
        """Return a configured value."""
        return self.values[key]

    def set(self, key: str, value: Any) -> None:
        """Store an updated value."""
        self.values[key] = value


def test_edit_info_widget_keeps_html_source_for_editing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that EditInfoWidget preserves the HTML source for editing."""
    config = _DummyConfig({"info_text": "<b>Hello</b>"})
    monkeypatch.setattr(custom_widgets.Settings, "get_instance", lambda: config)

    widget = custom_widgets.EditInfoWidget()
    widget.load()

    assert widget.info_text_browser.toPlainText() == "<b>Hello</b>"

    widget.info_text_browser.setPlainText("<i>Updated</i>")
    widget.save_button.click()

    assert config.values["info_text"] == "<i>Updated</i>"


def test_main_window_renders_info_text_as_html() -> None:
    """Test that the main window renders the info text as HTML."""
    config = _DummyConfig({"info_text": "<b>Hello</b>"})
    window = CoffeeBot.__new__(CoffeeBot)
    window.config = config

    info_field = Mock()
    window.info_field = info_field

    window._update_info(home=False)  # noqa: SLF001

    info_field.setHtml.assert_called_once_with("<b>Hello</b>")
