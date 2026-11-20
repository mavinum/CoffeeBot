"""
################################################################################

OS credential store integration for WebDAV credentials.

################################################################################
Copyright (C) 2026 Mavinum
SPDX-License-Identifier: GPL-3.0-only
See LICENSE in the project root.
################################################################################
"""

import keyring
from keyring.errors import KeyringError
from secretstorage.exceptions import SecretStorageException

SERVICE_NAME = "CoffeeBot"
WEBDAV_ACCOUNT = "webdav"


class CredentialStoreError(RuntimeError):
    """Raised when the operating-system credential store is unavailable."""

    def __init__(self, operation: str, reason: str | None = None) -> None:
        message = f"Could not {operation} the OS credential store"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


def get_webdav_credential() -> str | None:
    """Retrieve the saved WebDAV password or bearer token."""
    try:
        return keyring.get_password(SERVICE_NAME, WEBDAV_ACCOUNT)
    except (KeyringError, SecretStorageException) as exc:
        operation = "access"
        reason = str(exc)
        raise CredentialStoreError(operation, reason) from exc


def store_webdav_credential(credential: str) -> None:
    """Save a WebDAV password or bearer token in the OS credential store."""
    try:
        keyring.set_password(SERVICE_NAME, WEBDAV_ACCOUNT, credential)
    except (KeyringError, SecretStorageException) as exc:
        operation = "save to"
        reason = str(exc)
        raise CredentialStoreError(operation, reason) from exc
