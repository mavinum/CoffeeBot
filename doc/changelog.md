# Changelog

## [1.0.1] - 2026-11-23

### Fixed
- Manual update checks now work when automatic checks are disabled and show a completion status when the installed version is current.
- Spin boxes with hidden buttons display their values and accept keyboard input.

## [1.0.0] - 2026-11-19

Initial public release of CoffeeBot

### Implemented
- Linux desktop application for managing users, account balances, and beverage purchases
- Configurable beverage categories and prices
- Usage statistics and CSV/XLSX data exports
- Local SQLite storage, including automatic migration of legacy user databases
- WebDAV backups with credential stored in OS keyring
- `coffeebot-launch` for service-aware launching and `coffeebot-shortcut` for creating a desktop shortcut and `coffeebot-migrate` for importing user databases or config files
- `uv tool install coffeebot` installation, with PyPI publishing and version checks through GitHub Actions

### Compatibility
- Python 3.14.x on Raspbery Pi OS 13 (Trixie)

### Known limitations
- Telegram integration is not available in this release
