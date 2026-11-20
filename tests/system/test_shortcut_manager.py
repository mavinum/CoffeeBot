# Copyright (C) 2026 Mavinum
# SPDX-License-Identifier: GPL-3.0-only


from coffeebot.system import shortcut_manager
from coffeebot.system.systemd_manager import SystemdConfig, SystemdManager


def test_launch_app_restarts_active_service(monkeypatch) -> None:
    """Restart the systemd service when it is already active."""
    calls = []

    class ManagerStub:
        service_exists = True
        service_running = True
        service_enabled = False

        def restart(self):
            calls.append("restart")
            return True, "Restarting."

    monkeypatch.setattr(shortcut_manager.Settings, "configure_app", lambda *_args: None)
    monkeypatch.setattr(shortcut_manager, "SystemdManager", ManagerStub)

    assert shortcut_manager.launch_app() == 0
    assert calls == ["restart"]


def test_launch_app_starts_process_if_service_is_not_active_or_enabled(monkeypatch) -> None:
    """Launch the regular app process when the service is inactive and disabled."""
    launched = []

    class ManagerStub:
        service_exists = True
        service_running = False
        service_enabled = False

    monkeypatch.setattr(shortcut_manager.Settings, "configure_app", lambda *_args: None)
    monkeypatch.setattr(shortcut_manager, "SystemdManager", ManagerStub)
    monkeypatch.setattr(shortcut_manager, "_find_executable", lambda _name: "/home/user/.local/bin/coffeebot")
    monkeypatch.setattr(shortcut_manager.os, "execv", lambda path, args: launched.append((path, args)))

    assert shortcut_manager.launch_app() == 0
    assert launched == [("/home/user/.local/bin/coffeebot", ["/home/user/.local/bin/coffeebot"])]


def test_launch_app_reports_service_restart_failure(monkeypatch) -> None:
    """Return a failure instead of starting a duplicate process after restart fails."""

    class ManagerStub:
        service_exists = True
        service_running = False
        service_enabled = True

        def restart(self):
            return False, "Restart failed."

    monkeypatch.setattr(shortcut_manager.Settings, "configure_app", lambda *_args: None)
    monkeypatch.setattr(shortcut_manager, "SystemdManager", ManagerStub)
    monkeypatch.setattr(shortcut_manager, "_find_executable", lambda _name: None)

    assert shortcut_manager.launch_app() == 1


def test_service_status_checks_use_systemctl_unit_arguments(monkeypatch, tmp_path) -> None:
    """Query service states with systemctl's expected unit argument syntax."""
    commands = []

    class TestSettings:
        app_name = "CoffeeBot"

    monkeypatch.setattr(
        "coffeebot.system.systemd_manager.Settings.get_instance",
        TestSettings,
    )
    monkeypatch.setattr(SystemdConfig, "_find_executable", lambda _self: "/usr/bin/coffeebot")
    manager = SystemdManager(config=SystemdConfig())
    manager.service_file = tmp_path / "coffeebot.service"
    manager.service_file.touch()
    monkeypatch.setattr(manager, "_run_cmd", lambda command: (commands.append(command) or True, ""))

    assert manager.service_running
    assert manager.service_enabled
    assert commands == [
        ["systemctl --user is-active --quiet coffeebot.service"],
        ["systemctl --user is-enabled --quiet coffeebot.service"],
    ]
