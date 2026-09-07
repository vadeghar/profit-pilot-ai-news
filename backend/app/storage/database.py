from pathlib import Path

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS news_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    symbols_json TEXT NOT NULL DEFAULT '[]',
    materiality REAL NOT NULL DEFAULT 0 CHECK (materiality >= 0 AND materiality <= 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_event_id TEXT NOT NULL REFERENCES news_events(id),
    signal TEXT NOT NULL CHECK (signal IN ('BUY', 'SELL', 'IGNORE')),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reasoning TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    input_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_orders (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES news_events(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    fill_price REAL NOT NULL CHECK (fill_price > 0),
    notional REAL NOT NULL CHECK (notional > 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL,
    average_price REAL NOT NULL DEFAULT 0 CHECK (average_price >= 0),
    realized_pnl REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_news_events_published_at ON news_events(published_at);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_news_event_id ON ai_decisions(news_event_id);
CREATE INDEX IF NOT EXISTS idx_paper_orders_event_id ON paper_orders(event_id);
CREATE INDEX IF NOT EXISTS idx_paper_orders_created_at ON paper_orders(created_at);
"""


class SqliteDatabase:
    def __init__(self, database_url: str) -> None:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("SQLite database URL must start with sqlite:///")
        self.path = Path(database_url[len(prefix):])

    def connect(self) -> sqlite3.Connection:
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def check(self) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1").fetchone() is not None
