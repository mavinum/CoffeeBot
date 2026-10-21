import bcrypt
import pytest

from coffeebot.auth import verify_password


def test_password_check_accepts_correct_password_and_rejects_wrong_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify passwords using the stored bcrypt hash."""
    password_hash = bcrypt.hashpw(b"secret", bcrypt.gensalt(rounds=4)).decode("utf-8")

    class DummySettings:
        def get(self, key, default=None):
            return password_hash if key == "master_pwd_hash" else default

    monkeypatch.setattr("coffeebot.auth.Settings.get_instance", DummySettings)

    assert verify_password("secret") is True
    assert verify_password("wrong") is False
