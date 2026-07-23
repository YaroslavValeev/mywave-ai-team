# Phase 8.3: Idempotency receipts для boundary POST. Key = (operation, request_id).
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None
_memory: dict[tuple[str, str], dict[str, Any]] = {}  # fallback in-memory


def _db_path() -> Optional[str]:
    p = os.getenv("MOLT_IDEMPOTENCY_SQLITE_PATH") or os.getenv("CANONICAL_SQLITE_PATH")
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
            """CREATE TABLE IF NOT EXISTS idempotency_receipts (
                operation TEXT NOT NULL,
                request_id TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                trace_id TEXT,
                PRIMARY KEY (operation, request_id)
            )"""
        )
        _conn.commit()
        return _conn
    except Exception as e:
        logger.warning("idempotency SQLite init failed: %s", e)
        return None


def get_receipt(operation: str, request_id: str) -> Optional[dict[str, Any]]:
    """Возвращает сохранённый response или None."""
    conn = _get_conn()
    if conn:
        try:
            row = conn.execute(
                "SELECT response_json FROM idempotency_receipts WHERE operation = ? AND request_id = ?",
                (operation, request_id),
            ).fetchone()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.warning("idempotency get_receipt failed: %s", e)
        return None
    return _memory.get((operation, request_id))


def put_receipt(operation: str, request_id: str, response: dict[str, Any], trace_id: Optional[str] = None) -> None:
    """Сохраняет response как receipt."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = _get_conn()
    if conn:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO idempotency_receipts (operation, request_id, response_json, created_at, trace_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (operation, request_id, json.dumps(response), now, trace_id),
            )
            conn.commit()
        except Exception as e:
            logger.warning("idempotency put_receipt failed: %s", e)
    else:
        _memory[(operation, request_id)] = response
