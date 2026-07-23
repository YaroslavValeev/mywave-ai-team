# Персистентный runtime state для canonical path (ADR-010, Phase 6.5).
# Хранит mapping legacy_task_id -> {canonical_task_id, run_id, approval_id, status, last_event}.
# Позволяет approve callback восстанавливать контекст после рестарта без in-memory кэша.
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class InMemoryRuntimeStateStore:
    """In-memory store для тестов (при CANONICAL_STORAGE=memory)."""

    def __init__(self) -> None:
        self._data: Dict[tuple, dict] = {}

    def _key(self, source_system: str, legacy_task_id: str) -> tuple:
        return (source_system, str(legacy_task_id))

    def upsert(self, source_system: str, legacy_task_id: str, **updates: Any) -> None:
        key = self._key(source_system, legacy_task_id)
        row = self._data.get(key, {})
        row["updated_at"] = datetime.utcnow().isoformat()
        allowed = {"canonical_task_id", "run_id", "approval_id", "status", "last_event"}
        for k, v in updates.items():
            if k in allowed:
                row[k] = v  # None explicitly clears
        self._data[key] = row

    def get(self, source_system: str, legacy_task_id: str) -> Optional[dict]:
        key = self._key(source_system, legacy_task_id)
        return self._data.get(key)


class SQLiteRuntimeStateStore:
    """Persistent runtime state на SQLite. Та же БД, что canonical storage / crosswalk."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.row_factory = sqlite3.Row
            self._create_table()
        return self._conn

    @contextmanager
    def _cursor(self):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _create_table(self) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS canonical_runtime_state (
                source_system TEXT NOT NULL,
                legacy_task_id TEXT NOT NULL,
                canonical_task_id TEXT,
                run_id TEXT,
                approval_id TEXT,
                status TEXT,
                last_event TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_system, legacy_task_id)
            )
        """)
        conn.commit()

    def upsert(self, source_system: str, legacy_task_id: str, **updates: Any) -> None:
        now = datetime.utcnow().isoformat()
        legacy_key = str(legacy_task_id)
        allowed = {"canonical_task_id", "run_id", "approval_id", "status", "last_event"}
        updates = {k: v for k, v in updates.items() if k in allowed}  # None explicitly clears

        with self._cursor() as cur:
            cur.execute(
                """
                SELECT canonical_task_id, run_id, approval_id, status, last_event
                FROM canonical_runtime_state
                WHERE source_system = ? AND legacy_task_id = ?
                """,
                (source_system, legacy_key),
            )
            row = cur.fetchone()
            if row:
                data = dict(row)
            else:
                data = {}

            data.update(updates)
            data["updated_at"] = now

            cur.execute(
                """
                INSERT OR REPLACE INTO canonical_runtime_state
                (source_system, legacy_task_id, canonical_task_id, run_id, approval_id, status, last_event, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_system,
                    legacy_key,
                    data.get("canonical_task_id"),
                    data.get("run_id"),
                    data.get("approval_id"),
                    data.get("status"),
                    data.get("last_event"),
                    now,
                ),
            )

    def get(self, source_system: str, legacy_task_id: str) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT canonical_task_id, run_id, approval_id, status, last_event, updated_at
                FROM canonical_runtime_state
                WHERE source_system = ? AND legacy_task_id = ?
                """,
                (source_system, str(legacy_task_id)),
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
