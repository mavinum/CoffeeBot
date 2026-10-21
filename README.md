# Coffeebot

[![CI](https://github.com/mavinum/CoffeeBot/actions/workflows/ci.yml/badge.svg)](https://github.com/mavinum/CoffeeBot/actions)
[![PyPI version](https://img.shields.io/pypi/v/coffeebot)](https://pypi.org/project/coffeebot/)

CoffeeBot is a lightweight open source coffee and beverage billing companion for shared spaces.<br>
It helps teams track purchases, manage users and bring the classic "tick list" to the digital age. All you need is a RaspberryPi with touchscreen.

## Features
- **User management** – create, edit, and remove users
- **Flexible pricing** – configure per‑category rates or custom price tables
- **Statistics & reports** – view daily, weekly, and monthly spend summaries; export to CSV, Excel
- **WebDAV backups** – automatic remote backups keep your data safe
- **Modern and intuitive GUI** – built with PyQt6 for Linux
- **Telegram integration** – coming soon; Telegram connectivity is not available in this release
- **Small footprint** – intended for use on a Raspberry Pi with touchscreen


## Download / Install
Use uv to install on your system (recommended):

`uv tool install coffeebot`

After installation, start the app via the `coffeebot` entry point.

If you don't have uv installed yet, see the [installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Alternatively, you can also clone this repository and run coffeebot manually:

```bash
git clone https://github.com/mavinum/CoffeeBot.git
cd CoffeeBot
uv sync
uv run coffeebot
```
Instead of the `uv run coffeebot` command, you can also simply use the provided `coffeebot` entry point.

## Documentation
- [Operator guide: data privacy](https://github.com/mavinum/CoffeeBot/blob/master/doc/OPERATORS_DATA_PRIVACY.md)

## Source Code
The project is open source on GitHub:
https://github.com/mavinum/CoffeeBot

## Issue Tracker
Please report bugs or feature requests via the GitHub Issues page:
https://github.com/mavinum/CoffeeBot/issues

## License
This project is licensed under the GNU General Public License version 3.0 only.
See the [LICENSE](https://github.com/mavinum/CoffeeBot/blob/master/LICENSE).

## Third-Party Notices
This project uses third-party software and libraries. See the [third-party notices](https://github.com/mavinum/CoffeeBot/blob/master/doc/THIRD_PARTY_NOTICES.md).

## Warranty Disclaimer
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 only.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License v3.0](https://github.com/mavinum/CoffeeBot/blob/master/LICENSE) for the full license terms.

## Copyright
Copyright (c) 2026 Mavinum

## Contact
For other questions, email [Mavinum](mailto:mavinum@tutanota.de).
