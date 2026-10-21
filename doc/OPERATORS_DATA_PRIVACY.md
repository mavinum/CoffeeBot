# Operator Guide: Data Privacy

This guide describes the personal and operational data that CoffeeBot handles and the steps an operator should consider before using it with real users. It describes the current application behavior; it is not a privacy-compliance certification or legal advice.

## Operator responsibility

CoffeeBot is a software for local installation. It does not determine which privacy laws apply to an installation or ensure that the operator complies with them. **It is solely the responsibility of each operator to assess the applicable requirements and ensure that data privacy is enforced for their deployment.** This includes choosing a lawful purpose and basis for processing, giving users appropriate information, limiting access, setting retention periods, handling requests, and securing all copies and transfers of data.

Telegram signup and bot messaging are not available in this release. No data is sent to or received from Telegram by the current release. If Telegram functionality is added in a future release, this guide and the operator's privacy notice should be reviewed before enabling it.

## Data CoffeeBot handles

Depending on enabled features and operator usage, CoffeeBot can process:

- User profile data: forename, surname, workgroup or division, email address, and an optional Telegram Chat-ID entered in the user form. The Telegram ID field is retained for compatibility with legacy versions; it is not used to connect to Telegram in this release.
- Account and financial records: current balance and bookkeeping entries with timestamps, previous/new balances, deposits, and a user ID linking those balance transactions to an account.
- Consumption statistics: timestamp, beverage category, and price. These rows are not linked to a user account and do not store a user ID.
- Application settings: prices, categories, display preferences, and other operational settings. Settings can also contain WebDAV credentials when that integration is configured. A settings file carried over from an older installation may still contain unused Telegram settings; remove credentials that are no longer needed.
- Authentication data: a bcrypt password hash for the optional application master password. The password itself is not stored by this feature.
- Logs: operational events and errors. Routine application logs omit user profile fields and transaction values. Raw exception messages may still contain contextual information; restrict access to logs as a precaution.
- Exports: CSV/XLSX user exports contain ID, name, group, email, and balance. They currently omit Telegram ID.

User information entered into profile fields may be inaccurate or contain additional details; operators should not assume fields contain only the expected values.

## Where data is stored and sent

- **Local files:** CoffeeBot uses operating-system-specific user configuration, data, and log directories. The database is normally `user_data.db` in the application data directory; settings are held in a JSON configuration file in the application configuration directory; logs are written under the application log directory. The exact locations depend on the operating system and platform settings.
- **Local exports:** CSV/XLSX files are written to the destination selected by the operator. Treat these files as separate copies of the database data and protect or delete them accordingly.
- **Telegram:** The current release does not connect to Telegram or transmit profile data to it. The optional Telegram Chat-ID field is stored locally in the user profile and is currently unused by the application.
- **WebDAV:** When configured, WebDAV export can upload CSV/XLSX exports. Automatic or manual backups can upload the SQLite database, logs, and settings file to the configured server. Those files can include personal data and credentials. The WebDAV provider and anyone with access to that account or server may therefore have access to the uploaded copies.

CoffeeBot stores its local database and JSON settings as files; the application does not encrypt those files at rest. The master-password hash does not encrypt the database or protect exported files. Restrict operating-system account and file access, and secure any removable media, backups, and WebDAV destination. Keep integration credentials confidential and use appropriately scoped credentials where possible.

## Retention, deletion, and user requests

CoffeeBot does not impose a data-retention schedule. The operator must decide how long each category is needed and remove data and copies when appropriate under the rules that apply to their deployment.

Deleting a user through the application removes the user profile row, but does not automatically delete linked bookkeeping rows. Consumption statistics are not linked to individual accounts, and deleting a user does not remove those rows. Database backups, log files, exported files, and remote backups are also not automatically purged when a user is removed. Plan and verify deletion across these locations; do not promise that deleting an account erases all associated data.
