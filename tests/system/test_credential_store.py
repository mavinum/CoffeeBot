# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only

from datetime import datetime
from pathlib import Path

import keyring.errors
import pytest
from secretstorage.exceptions import SecretStorageException

from coffeebot.system import credential_store, webdav_manager
from coffeebot.system.credential_store import CredentialStoreError


def test_webdav_credential_is_read_from_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Store and retrieve the secret through the OS keyring API."""
    saved: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        credential_store.keyring,
        "set_password",
        lambda service, account, credential: saved.__setitem__((service, account), credential),
    )
    monkeypatch.setattr(
        credential_store.keyring, "get_password", lambda service, account: saved.get((service, account))
    )

    credential_store.store_webdav_credential("test-token")

    assert credential_store.get_webdav_credential() == "test-token"


def test_webdav_credential_store_errors_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convert keyring failures into an actionable credential-store error."""

    def fail_to_store(*_args) -> None:
        raise keyring.errors.KeyringError

    monkeypatch.setattr(credential_store.keyring, "set_password", fail_to_store)

    with pytest.raises(CredentialStoreError, match="Could not save to the OS credential store"):
        credential_store.store_webdav_credential("test-token")


def test_secret_service_errors_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convert Secret Service D-Bus failures into credential-store errors."""

    def fail_to_read(*_args) -> None:
        raise SecretStorageException

    monkeypatch.setattr(credential_store.keyring, "get_password", fail_to_read)

    with pytest.raises(CredentialStoreError, match="Could not access the OS credential store"):
        credential_store.get_webdav_credential()


@pytest.mark.parametrize(
    ("username", "expected_client_args"),
    [
        ("coffee-user", {"auth": ("coffee-user", "test-token")}),
        ("", {"headers": {"Authorization": "Bearer test-token"}}),
    ],
)
def test_webdav_client_uses_keyring_credential(
    monkeypatch: pytest.MonkeyPatch, username: str, expected_client_args: dict[str, object]
) -> None:
    """Pass keyring credentials to WebDAV using the configured authentication mode."""
    settings = {"webdav_url": "https://webdav.example.invalid/", "webdav_user": username}
    client_args: dict[str, object] = {}

    class TestSettings:
        def get(self, key: str, default=None):
            return settings.get(key, default)

    class TestClient:
        def __init__(self, **kwargs: object) -> None:
            client_args.update(kwargs)

        def mkdir(self, _path: str) -> None:
            pass

        def exists(self, _path: str) -> bool:
            return False

        def upload_file(self, _local_path, _remote_path: str) -> None:
            pass

    def create_client(**kwargs: object) -> TestClient:
        return TestClient(**kwargs)

    monkeypatch.setattr(webdav_manager.Settings, "get_instance", TestSettings)
    monkeypatch.setattr(webdav_manager, "get_webdav_credential", lambda: "test-token")
    monkeypatch.setattr(webdav_manager, "Client", create_client)

    worker = webdav_manager.WebDavWorker()
    export_results: list[tuple[bool, str]] = []
    worker.export_finished.connect(lambda success, message: export_results.append((success, message)))
    worker.upload_export(Path("test-export.csv"))

    assert export_results == [(True, "Export test-export.csv uploaded successfully.")]
    assert client_args == {"base_url": "https://webdav.example.invalid/", **expected_client_args}


def test_webdav_client_requires_a_saved_keyring_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not initialize the WebDAV client with a missing credential."""

    class EmptySettings:
        def get(self, _key: str, default=None):
            return default

    monkeypatch.setattr(webdav_manager.Settings, "get_instance", EmptySettings)
    monkeypatch.setattr(webdav_manager, "get_webdav_credential", lambda: None)

    export_results: list[tuple[bool, str]] = []
    worker = webdav_manager.WebDavWorker()
    worker.export_finished.connect(lambda success, message: export_results.append((success, message)))
    worker.upload_export(Path("test-export.csv"))

    assert export_results == [(False, "Could not load the OS credential store: No WebDAV password or token is saved.")]


def test_webdav_backup_uploads_database_logs_and_settings_without_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Upload configured backup files while keeping the credential outside settings."""
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir()
    logs_dir.mkdir()
    database = data_dir / "users.db"
    database.write_text("test database", encoding="utf-8")
    log_file = logs_dir / "coffeebot.log"
    log_file.write_text("test log", encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text('{"webdav_url": "https://webdav.example.invalid/"}', encoding="utf-8")
    settings = {
        "webdav_url": "https://webdav.example.invalid/",
        "webdav_user": "coffee-user",
        "data_dir": str(data_dir),
        "db_file": database.name,
        "log_dir": str(logs_dir),
    }
    uploaded: list[tuple[Path, str]] = []
    finished_results: list[tuple[bool, str]] = []

    class TestSettings:
        path = config_path

        def get(self, key: str, default=None):
            return settings.get(key, default)

    class TestClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def mkdir(self, _path: str) -> None:
            pass

        def exists(self, _path: str) -> bool:
            return False

        def upload_file(self, local_path: Path, remote_path: str) -> None:
            uploaded.append((local_path, remote_path))

    monkeypatch.setattr(webdav_manager.Settings, "get_instance", TestSettings)
    monkeypatch.setattr(webdav_manager, "get_webdav_credential", lambda: "test-token")
    monkeypatch.setattr(webdav_manager, "Client", TestClient)

    worker = webdav_manager.WebDavWorker()
    worker.finished.connect(lambda success, message: finished_results.append((success, message)))
    worker.run_backup()

    assert finished_results == [(True, "Backup completed successfully.")]
    assert {remote for _, remote in uploaded} == {
        "db/coffee_users_" + datetime.now().strftime("%Y-%m") + ".db",
        "logs/coffeebot.log",
        "config.json",
    }
    assert (config_path, "config.json") in uploaded
    assert "test-token" not in config_path.read_text(encoding="utf-8")
