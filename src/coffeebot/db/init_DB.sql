BEGIN;
CREATE TABLE IF NOT EXISTS users(
  id          INTEGER PRIMARY KEY,
  forename    TEXT,
  surename    TEXT,
  workgroup   TEXT,
  email       TEXT,
  telegram_id INT,
  balance     REAL
);

CREATE TABLE IF NOT EXISTS user_stats(
  process_id  INTEGER PRIMARY KEY, 
  timestamp   TEXT NOT NULL,
  category    TEXT NOT NULL,
  price       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS bookkeeping(
  transaction_id  INTEGER PRIMARY KEY, 
  timestamp       TEXT NOT NULL,
  balance_old     TEXT,
  balance_new     REAL NOT NULL,
  deposit         REAL NOT NULL,
  user_id         INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

COMMIT;