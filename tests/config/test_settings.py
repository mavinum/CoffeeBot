# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDoubleSpinBox, QLabel, QPushButton

from coffeebot.config.settings import Settings
from coffeebot.gui.widgets.settings_widget import SettingsWidget


@pytest.fixture(autouse=True)
def mock_systemd_manager(monkeypatch: pytest.MonkeyPatch):
    """Prevent SettingsWidget from interacting with actual systemd services."""

    class DummySystemdManager:
        def __init__(self, *args, **kwargs):
            pass

        def enable(self, *args, **kwargs):
            pass

        def disable(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self, *args, **kwargs):
            pass

        def restart(self, *args, **kwargs):
            pass

        def status(self):
            return "active"

        service_enabled = False

    monkeypatch.setattr("coffeebot.gui.widgets.settings_widget.SystemdManager", DummySystemdManager)


def test_settings_uses_default_json_when_custom_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that settings fallback to default JSON when custom config is missing."""
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.4.0")
    default_path = tmp_path / "default.json"
    default_path.write_text('{"theme": "dark", "timeout": 5}', encoding="utf-8")
    config_dir = tmp_path / "config"

    settings = Settings.configure_app(
        "CoffeeBotTest",
        "Mavinum",
        config_dir=config_dir,
        default_path=default_path,
        config_filename="app-settings.json",
    )

    assert settings.get("theme") == "dark"
    assert settings.get("timeout") == 5
    assert (config_dir / "app-settings.json").exists()


def test_settings_merges_custom_values_on_top_of_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that custom settings are merged on top of defaults."""
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.4.0")
    default_path = tmp_path / "default.json"
    default_path.write_text('{"theme": "dark", "timeout": 5}', encoding="utf-8")
    config_dir = tmp_path / "config"
    config_path = config_dir / "app-settings.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text('{"theme": "light"}', encoding="utf-8")

    settings = Settings.configure_app(
        "CoffeeBotTestCustom",
        "Mavinum",
        config_dir=config_dir,
        default_path=default_path,
        config_filename="app-settings.json",
    )

    assert settings.get("theme") == "light"
    assert settings.get("timeout") == 5
    assert json.loads(config_path.read_text(encoding="utf-8"))["theme"] == "light"


@pytest.mark.usefixtures("qapp")
def test_settings_widget_load_and_save_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SettingsWidget can load and save settings correctly."""
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.4.0")
    default_path = tmp_path / "default.json"
    config_dir = tmp_path / "config"
    default_path.write_text(
        f'{{"cat_1_price": 0.4, "data_dir": "{config_dir}", "logo_file": "logo.png"}}', encoding="utf-8"
    )

    Settings.configure_app(
        "coffeebot", "Mavinum", config_dir=config_dir, default_path=default_path, config_filename="app-settings.json"
    )

    widget = SettingsWidget()
    widget.load()

    cat_spin = widget.findChild(QDoubleSpinBox, "cat_1_price_spin")

    assert cat_spin is not None

    cat_spin.setValue(1.25)
    widget.save_button.click()

    assert Settings.get_instance().get("cat_1_price") == 1.25


@pytest.mark.usefixtures("qapp")
def test_settings_widget_builds_about_tab(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that the about tab in SettingsWidget is correctly constructed."""
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.4.0")
    Settings.configure_app(
        "CoffeeBot", "Mavinum", config_dir=tmp_path / "config", default_path=tmp_path / "default.json"
    )
    widget = SettingsWidget()

    title_label = widget.findChild(QLabel, "about_title_label")
    description_label = widget.findChild(QLabel, "label_3")
    repo_button = widget.findChild(QPushButton, "about_repo_button")

    assert title_label is not None
    assert description_label is not None
    assert repo_button is not None
    assert title_label.text().lower() == "coffeebot"
    assert "open source" in description_label.text().lower()
