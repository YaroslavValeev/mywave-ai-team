# Phase 8.4: Boundary request journal (audit trail). SQLite-backed.
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None
_max_entries = 10_000
_cap_entries = int(os.getenv("MOLT_JOURNAL_MAX_ENTRIES", str(_max_entries)))


def _db_path() -> Optional[str]:
    p = os.getenv("MOLT_JOURNAL_SQLITE_PATH") or os.getenv("MOLT_IDEMPOTENCY_SQLITE_PATH") or os.getenv("CANONICAL_SQLITE_PATH")
    return (p or "").strip() or None


def _get_conn() -> Optional[sqlite3.Connection]:
    global _conn
    if _conn is not None:
        return _conn
    path = _db_path()
    if not path:
        return None
    try:
        _conn = sqlite3.connect(path, timeout=10)
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS boundary_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                trace_id TEXT,
                operation TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                deduplicated INTEGER NOT NULL,
                status TEXT,
                error_type TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                duration_ms REAL
            )"""
        )
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_request_id ON boundary_journal(request_id)")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_created_at ON boundary_journal(created_at)")
        _conn.commit()
        return _conn
    except Exception as e:
        logger.warning("request_journal SQLite init failed: %s", e)
        return None


def append(
    request_id: str,
    operation: str,
    endpoint: str,
    accepted: bool,
    deduplicated: bool,
    duration_ms: float,
    trace_id: Optional[str] = None,
    status: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    conn = _get_conn()
    if not conn:
        return
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            """INSERT INTO boundary_journal
               (request_id, trace_id, operation, endpoint, accepted, deduplicated, status, error_type, error_message, created_at, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id,
                trace_id or "",
                operation,
                endpoint,
                1 if accepted else 0,
                1 if deduplicated else 0,
                status or "",
                error_type or "",
                (error_message or "")[:500],
                now,
                duration_ms,
            ),
        )
        conn.commit()
        if _cap_entries > 0:
            cur = conn.execute("SELECT COUNT(*) FROM boundary_journal")
            n = cur.fetchone()[0]
            if n > _cap_entries:
                conn.execute("DELETE FROM boundary_journal WHERE id IN (SELECT id FROM boundary_journal ORDER BY id LIMIT ?)", (n - _cap_entries,))
                conn.commit()
    except Exception as e:
        logger.warning("request_journal append failed: %s", e)


def get_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Последние записи (для inspection script)."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        rows = conn.execute(
            """SELECT request_id, trace_id, operation, endpoint, accepted, deduplicated, status, error_type, error_message, created_at, duration_ms
               FROM boundary_journal ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "request_id": r[0],
                "trace_id": r[1] or None,
                "operation": r[2],
                "endpoint": r[3],
                "accepted": bool(r[4]),
                "deduplicated": bool(r[5]),
                "status": r[6] or None,
                "error_type": r[7] or None,
                "error_message": r[8] or None,
                "created_at": r[9],
                "duration_ms": r[10],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("request_journal get_recent failed: %s", e)
        return []
