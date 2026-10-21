"""
################################################################################

Systemd service manager for CoffeeBot.

Creates, modifies and controls systemd service configuration for coffeebot and
ensure compatibility with the deploy environment (e.g. Raspberry Pi displays).

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

import getpass
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from coffeebot.config.settings import Settings


@dataclass
class SystemdConfig:
    """Configuration data for the systemd service."""

    app: str = field(init=False)
    user: str = field(init=False)
    project_root: Path = field(init=False)
    executable_path: str = field(init=False)
    service_name: str = field(init=False)

    def __post_init__(self):
        self._settings = Settings.get_instance()
        self.app = self._settings.app_name.lower()
        self.user = getpass.getuser()
        self.project_root = Path(__file__).resolve().parents[3]
        self.service_name = f"{self.app}.service"
        self.executable_path = self._find_executable()

    def _find_executable(self) -> str:
        """Find the coffeebot executable path."""
        exe_path = shutil.which(self.app)
        if exe_path:
            return exe_path

        uv_path = f"/home/{self.user}/.local/bin/{self.app}"
        if Path(uv_path).exists():
            return uv_path

        msg = f"No such executable '{self.app}'"
        raise FileNotFoundError(msg)

    @property
    def base_content(self) -> str:
        """Generate the base systemd service unit file."""
        lines = [
            "[Unit]",
            f"Description={self.app.capitalize()} {self._settings.version}",
            "After=graphical-session.target",
            "PartOf=graphical-session.target",
            "",
            "[Service]",
            f"User={self.user}",
            f"WorkingDirectory={self.project_root}",
            "Environment=DISPLAY=:0",
            f"Environment=XAUTHORITY=/home/{self.user}/.Xauthority",
            f"ExecStart={self.executable_path}",
            "KillMode=process",
            "",
            "[Install]",
            "WantedBy=graphical-session.target",
        ]
        return "\n".join(lines)

    def get_override_content(self, restart: bool | None = None, restart_timeout: int | None = None) -> str:
        """Return content for override file to auto-restart and restart timout."""
        if restart is None:
            restart = bool(self._settings.get("auto_restart"))
        restart_mode = "always" if restart else "no"

        if restart_timeout is None:
            restart_timeout = int(str(self._settings.get("restart_timeout", 5)))

        lines = ["[Service]", f"Restart={restart_mode}", f"RestartSec={restart_timeout}s"]
        return "\n".join(lines)


class SystemdManager:
    """Handles the installation and control of the systemd service."""

    SYSTEMD_PATH = Path.home() / ".config" / "systemd" / "user/"

    def __init__(self, config: SystemdConfig | None = None):
        self.config = config if config is not None else SystemdConfig()
        self.service_file = self.SYSTEMD_PATH / self.config.service_name
        self.override_dir = self.SYSTEMD_PATH / f"{self.config.service_name}.d"
        self.override_file = self.override_dir / "override.conf"

    def _sanitize(self, name: str) -> str:
        """Ensure service names contain only alphanumeric characters, underscores, or dots."""
        if not re.match(r"^[a-zA-Z0-9._/ \-~]+$", name):
            return "unsafe"
        return name

    def _run_cmd(self, cmd_list: list[str]) -> tuple[bool, str]:
        """Execute commands via /bin/sh."""
        cmd_list = [self._sanitize(cmd) for cmd in cmd_list]
        if "unsafe" in cmd_list:
            return False, "Security risk: Unsafe characters!"
        cmd_chain = " && ".join(cmd_list)
        try:
            result = subprocess.run(["/bin/sh", "-c", cmd_chain], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            return False, exc.stderr.strip() or f"Error: {exc.returncode}"
        except Exception as exc:
            return False, str(exc)
        else:
            return result.returncode == 0, "Command finished without Errors."

    @property
    def service_exists(self) -> bool:
        """Return if service already exists."""
        return self.service_file.exists()

    @property
    def service_running(self) -> bool:
        """Return if service is active (running)."""
        cmd = [f"systemctl --user is-active --quiet show {self.config.service_name}"]
        success, _ = self._run_cmd(cmd)
        return success

    @property
    def service_enabled(self) -> bool:
        """Return if service is enabled."""
        cmd = [f"systemctl --user is-enabled --quiet show {self.config.service_name}"]
        success, _ = self._run_cmd(cmd)
        return success

    def install(self) -> tuple[bool, str]:
        """Install the base service and the initial override."""
        t_svc = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8")  # noqa: SIM115
        t_ovr = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8")  # noqa: SIM115

        svc_tmp, ovr_tmp = Path(t_svc.name), Path(t_ovr.name)
        try:
            t_svc.write(self.config.base_content)
            t_svc.close()
            t_ovr.write(self.config.get_override_content())
            t_ovr.close()

            cmd = [
                f"mkdir -p {self.override_dir}",
                f"mv {svc_tmp} {self.service_file}",
                f"mv {ovr_tmp} {self.override_file}",
                "systemctl --user daemon-reload",
                f"systemctl --user enable {self.config.service_name}",
            ]

            success, err = self._run_cmd(cmd)
        except OSError as exc:
            return False, f"File system error: {exc}"
        except Exception as exc:
            return False, f"Unexpected error: {exc}"
        finally:
            for p in (svc_tmp, ovr_tmp):
                if p.exists():
                    p.unlink()

        return (True, "Service installed successfully.") if success else (False, f"Installation failed: {err}")

    def update_overrides(self, auto_restart: bool, timeout: int) -> tuple[bool, str]:
        """Update dynamic parameters in the override file."""
        t_ovr = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8")  # noqa: SIM115
        ovr_tmp = Path(t_ovr.name)
        try:
            t_ovr.write(self.config.get_override_content(auto_restart, timeout))
            t_ovr.close()

            cmd = [
                f"mkdir -p {self.override_dir}",
                f"mv -f {ovr_tmp} {self.override_file}",
                "systemctl --user daemon-reload",
            ]
            success, err = self._run_cmd(cmd)
        except OSError as exc:
            return False, f"File system error: {exc}"
        except Exception as exc:
            return False, f"Unexpected error: {exc}"
        finally:
            if ovr_tmp.exists():
                ovr_tmp.unlink()

        return (True, "Crash restart settings updated!") if success else (False, f"Update failed: {err}")

    def restart(self) -> tuple[bool, str]:
        """Restart systemd service if exists."""
        if not self.service_exists:
            return False, "Service not installed."

        cmd = [f"systemctl --user restart {self.config.service_name}"]
        success, err = self._run_cmd(cmd)
        return (True, "Restarting.") if success else (False, f"Restart failed: {err}")

    def enable(self) -> tuple[bool, str]:
        """Enable the service if it exists."""
        if not self.service_exists:
            return False, "Service not installed."

        cmd = [f"systemctl --user enable {self.config.service_name}", "systemctl --user daemon-reload"]
        success, err = self._run_cmd(cmd)
        return (True, "Autostart enabled.") if success else (False, f"Enable failed: {err}")

    def disable(self) -> tuple[bool, str]:
        """Disable the service if it exists."""
        if not self.service_exists:
            return False, "Service not installed."

        cmd = [f"systemctl --user disable {self.config.service_name}", "systemctl --user daemon-reload"]
        success, err = self._run_cmd(cmd)
        return (True, "Autostart disabled.") if success else (False, f"Disable failed: {err}")

    def remove(self) -> tuple[bool, str]:
        """Completely remove the service and its overrides."""
        cmd = [
            f"systemctl --user disable {self.config.service_name}",
            f"rm -rf {self.override_dir}",
            f"rm {self.service_file}",
            "systemctl --user daemon-reload",
        ]
        success, err = self._run_cmd(cmd)
        return (True, "Autostart removed.") if success else (False, f"Removal failed: {err}")
