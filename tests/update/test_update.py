# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only

import asyncio
from functools import partial
from importlib import metadata
from pathlib import Path

import httpx
import pytest

from coffeebot.config.settings import Settings
from coffeebot.update.update_check import UpdateChecker
from coffeebot.update.update_manager import UpdateManager

pytestmark = pytest.mark.usefixtures("qapp")


def test_update_checker_is_newer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that UpdateChecker correctly identifies newer versions."""
    monkeypatch.setattr(metadata, "version", lambda _app_name: "1.0.0")
    default_path = tmp_path / "default.json"
    default_path.write_text('{"bot_startup": false}', encoding="utf-8")
    Settings.configure_app(
        "coffeebot-test-update",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=default_path,
        config_filename="settings.json",
    )
    checker = UpdateChecker(auto_check=False)

    assert checker._is_newer("1.0.1") is True  # noqa: SLF001
    assert checker._is_newer("1.0.0") is False  # noqa: SLF001
    assert checker._is_newer("0.9.9") is False  # noqa: SLF001


def test_update_checker_fetch_latest_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test fetching the latest version from PyPi."""
    monkeypatch.setattr(metadata, "version", lambda _app_name: "1.0.0")
    default_path = tmp_path / "default.json"
    default_path.write_text('{"bot_startup": false}', encoding="utf-8")
    Settings.configure_app(
        "coffeebot-test-update-fetch",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=default_path,
        config_filename="settings.json",
    )

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"info": {"version": "1.2.3"}}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url):
            return DummyResponse()

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)
    checker = UpdateChecker(auto_check=False)
    version = asyncio.run(checker._fetch_latest_version())  # noqa: SLF001

    assert version == "1.2.3"


def test_update_manager_upgrade_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test successful upgrade process."""
    monkeypatch.setattr(metadata, "version", lambda _app_name: "1.0.0")
    default_path = tmp_path / "default.json"
    default_path.write_text('{"bot_startup": false}', encoding="utf-8")
    Settings.configure_app(
        "coffeebot-test-update-manager",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=default_path,
        config_filename="settings.json",
    )

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*_args, **_kwargs):
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    completed = []
    finished = []
    failed = []

    manager = UpdateManager(on_restart=None)
    manager.upgrade_completed.connect(partial(completed.append, True))
    manager.upgrade_finished.connect(partial(finished.append, True))
    manager.upgrade_failed.connect(failed.append)

    manager.run()

    assert completed == [True]
    assert finished == [True]
    assert failed == []


def test_update_manager_upgrade_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Emit the failure signal when the package upgrade fails."""
    monkeypatch.setattr(metadata, "version", lambda _app_name: "1.0.0")
    default_path = tmp_path / "default.json"
    default_path.write_text('{"bot_startup": false}', encoding="utf-8")
    Settings.configure_app(
        "coffeebot-test-update-manager-fail",
        "Mavinum",
        config_dir=tmp_path / "config",
        default_path=default_path,
        config_filename="settings.json",
    )

    class Result:
        returncode = 1
        stdout = ""
        stderr = "upgrade failed"

    def fake_run(*_args, **_kwargs):
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    completed = []
    finished = []
    failed = []

    manager = UpdateManager(on_restart=None)
    manager.upgrade_completed.connect(partial(completed.append, True))
    manager.upgrade_finished.connect(partial(finished.append, True))
    manager.upgrade_failed.connect(failed.append)

    manager.run()

    assert completed == []
    assert finished == []
    assert failed == ["upgrade failed"]
