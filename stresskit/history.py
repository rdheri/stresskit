"""SQLite history logging and retrieval for StressKit.

Maintains a local SQLite database at ~/.stresskit/runs.db that stores
a summary row for each load test run. Supports the `stresskit history` command.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from stresskit.models import RunReport

DB_PATH = Path.home() / ".stresskit" / "runs.db"


def _get_connection() -> sqlite3.Connection:
    """Create or open the SQLite database and ensure the schema exists.

    Returns:
        An open sqlite3 Connection.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            url TEXT NOT NULL,
            method TEXT NOT NULL,
            concurrency INTEGER NOT NULL,
            total_requests INTEGER NOT NULL,
            successful_requests INTEGER NOT NULL,
            failed_requests INTEGER NOT NULL,
            elapsed_s REAL NOT NULL,
            rps REAL NOT NULL,
            mean_latency_ms REAL NOT NULL,
            p50_latency_ms REAL NOT NULL,
            p95_latency_ms REAL NOT NULL,
            p99_latency_ms REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def log_run(report: RunReport) -> None:
    """Insert a summary row for a completed run into the history database.

    Args:
        report: The completed run report to log.
    """
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
            (id, timestamp, url, method, concurrency, total_requests,
             successful_requests, failed_requests, elapsed_s, rps,
             mean_latency_ms, p50_latency_ms, p95_latency_ms, p99_latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.run_id,
                report.timestamp,
                report.config.url,
                report.config.method.value,
                report.config.concurrency,
                report.total_requests,
                report.successful_requests,
                report.failed_requests,
                report.total_elapsed_s,
                report.requests_per_second,
                report.latency.mean_ms,
                report.latency.p50_ms,
                report.latency.p95_ms,
                report.latency.p99_ms,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(limit: int = 20) -> list[dict[str, object]]:
    """Retrieve the most recent run summaries from the history database.

    Args:
        limit: Maximum number of runs to return.

    Returns:
        List of dictionaries, each representing a run summary, ordered
        by timestamp descending (most recent first).
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT id, timestamp, url, method, concurrency, total_requests,
                   successful_requests, failed_requests, elapsed_s, rps,
                   mean_latency_ms, p50_latency_ms, p95_latency_ms, p99_latency_ms
            FROM runs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def clear_history() -> int:
    """Delete all entries from the history database.

    Returns:
        Number of rows deleted.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM runs")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
