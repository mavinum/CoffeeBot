import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from coffeebot.config.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep settings state and platform data inside the per-test temporary directory."""

    class TemporaryPlatformDirs:
        def __init__(self, app_name: str, _vendor: str) -> None:
            self.user_data_path = tmp_path / app_name / "data"
            self.user_log_path = tmp_path / app_name / "logs"

    monkeypatch.setattr("coffeebot.config.settings.PlatformDirs", TemporaryPlatformDirs)
    monkeypatch.setattr(Settings, "_instance", None)
    monkeypatch.setattr(Settings, "dirs", None, raising=False)
    monkeypatch.setattr(Settings, "app_name", "")
    monkeypatch.setattr(Settings, "vendor", "")
    monkeypatch.setattr(Settings, "version", "")


@pytest.fixture
def qapp():
    """Reuse QApplication and close top-level widgets after each test."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    for widget in app.topLevelWidgets():
        widget.close()
    app.processEvents()
