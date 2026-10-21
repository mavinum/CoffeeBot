"""
################################################################################

Authentication utilities for CoffeeBot.

This module provides a thin wrapper around the `bcrypt` library to
store and verify a master password.  The hash is stored in the application
settings via the `Settings` class.
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

import bcrypt

from coffeebot.config.settings import Settings

_MASTER_HASH_KEY = "master_pwd_hash"


# region Public API


def set_master_password(password: str) -> None:
    """
    Hash ``password`` with bcrypt and store the hash.

    The hash string produced by `bcrypt.hashpw` already contains the
    salt, so it is enough to presist the resulting bytes.
    """
    if not password:
        msg = "Password must not be empty"
        raise ValueError(msg)

    # bcrypt requires bytes
    pw_bytes = password.encode("utf-8")
    # Generate a salt and hash the password
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    # Store the hash as a UTF-8 string
    Settings.get_instance().set(_MASTER_HASH_KEY, hashed.decode("utf-8"))


def verify_password(password: str) -> bool:
    """
    Return ``True`` if ``password`` matches the stored master password.

    If no password has been set yet, ``False`` is returned, except
    ``password`` is also an empty string.
    """
    stored_hash = Settings.get_instance().get(_MASTER_HASH_KEY, None)
    if stored_hash is None:
        # if password == "":
        #     return True
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), str(stored_hash).encode("utf-8"))
    except (ValueError, TypeError):
        return False


# end region


# Export the function on module level
__all__ = ["set_master_password", "verify_password"]
