from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS app_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_sms_date TEXT NOT NULL,
    cycle_started_at TEXT NOT NULL,
    snoozed_until TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    channel TEXT,
    stage TEXT,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_lookup
ON events(event_type, channel, status, created_at DESC);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self, initial_last_sms_date: date, now: datetime) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                """
                INSERT OR IGNORE INTO app_state
                    (id, last_sms_date, cycle_started_at, snoozed_until, updated_at)
                VALUES (1, ?, ?, NULL, ?)
                """,
                (
                    initial_last_sms_date.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

    def get_state(self) -> dict[str, str | None]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM app_state WHERE id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("database is not initialized")
        return dict(row)

    def mark_sms_sent(self, sent_date: date, now: datetime) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE app_state
                SET last_sms_date = ?, cycle_started_at = ?,
                    snoozed_until = NULL, updated_at = ?
                WHERE id = 1
                """,
                (sent_date.isoformat(), now.isoformat(), now.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO events
                    (event_type, channel, stage, status, message, created_at)
                VALUES ('sms_confirmed', 'web', NULL, 'success', ?, ?)
                """,
                (f"Confirmed SMS date: {sent_date.isoformat()}", now.isoformat()),
            )

    def snooze(self, until: datetime, now: datetime) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE app_state SET snoozed_until = ?, updated_at = ?
                WHERE id = 1
                """,
                (until.isoformat(), now.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO events
                    (event_type, channel, stage, status, message, created_at)
                VALUES ('snoozed', 'web', NULL, 'success', ?, ?)
                """,
                (f"Snoozed until: {until.isoformat()}", now.isoformat()),
            )

    def add_event(
        self,
        *,
        event_type: str,
        channel: str | None,
        stage: str | None,
        status: str,
        message: str,
        now: datetime,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events
                    (event_type, channel, stage, status, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    channel,
                    stage,
                    status,
                    message[:2000],
                    now.isoformat(),
                ),
            )

    def last_successful_notification(
        self, channel: str, cycle_started_at: datetime
    ) -> tuple[datetime, str | None] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT created_at, stage FROM events
                WHERE event_type = 'reminder'
                  AND channel = ?
                  AND status = 'success'
                  AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (channel, cycle_started_at.isoformat()),
            ).fetchone()
        if row is None:
            return None
        return datetime.fromisoformat(row["created_at"]), row["stage"]

    def event_exists(self, event_type: str, message: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM events
                WHERE event_type = ? AND message = ? AND status = 'success'
                LIMIT 1
                """,
                (event_type, message),
            ).fetchone()
        return row is not None

    def recent_events(self, limit: int = 50) -> list[dict[str, str | None]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def backup(self, backup_dir: Path, now: datetime, retention_days: int) -> Path:
        backup_dir.mkdir(parents=True, exist_ok=True)
        destination = backup_dir / f"reminder-{now:%Y%m%d}.db"
        with closing(sqlite3.connect(self.path)) as source:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)

        cutoff = now.date() - timedelta(days=retention_days)
        for candidate in backup_dir.glob("reminder-*.db"):
            try:
                file_date = date.fromisoformat(
                    f"{candidate.stem[9:13]}-{candidate.stem[13:15]}-{candidate.stem[15:17]}"
                )
            except (ValueError, IndexError):
                continue
            if file_date < cutoff:
                candidate.unlink(missing_ok=True)
        return destination
