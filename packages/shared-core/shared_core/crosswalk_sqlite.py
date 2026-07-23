# Персистентный crosswalk на SQLite (ADR-008). Та же семантика, что CrosswalkStore.
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple

from shared_core.crosswalk import CrosswalkEntry


class SQLiteCrosswalkStore:
    """Crosswalk legacy_id <-> canonical_id с хранением в SQLite."""

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
            CREATE TABLE IF NOT EXISTS crosswalk (
                source_system TEXT NOT NULL,
                legacy_entity_type TEXT NOT NULL,
                legacy_id TEXT NOT NULL,
                canonical_entity_type TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (source_system, legacy_entity_type, legacy_id)
            )
        """)
        conn.commit()

    def register(
        self,
        source_system: str,
        legacy_entity_type: str,
        legacy_id: str,
        canonical_entity_type: str,
        canonical_id: str,
        created_at: Optional[object] = None,
    ) -> CrosswalkEntry:
        from datetime import datetime
        now_dt = datetime.utcnow()
        if created_at is not None:
            if isinstance(created_at, datetime):
                now_dt = created_at
            elif isinstance(created_at, str):
                try:
                    now_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    pass
        now_str = now_dt.isoformat()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO crosswalk
                (source_system, legacy_entity_type, legacy_id, canonical_entity_type, canonical_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_system, legacy_entity_type, str(legacy_id), canonical_entity_type, canonical_id, now_str),
            )
        return CrosswalkEntry(
            source_system=source_system,
            legacy_entity_type=legacy_entity_type,
            legacy_id=str(legacy_id),
            canonical_entity_type=canonical_entity_type,
            canonical_id=canonical_id,
            created_at=now_dt,
        )

    def get_canonical(
        self,
        source_system: str,
        legacy_entity_type: str,
        legacy_id: str,
    ) -> Optional[str]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT canonical_id FROM crosswalk
                WHERE source_system = ? AND legacy_entity_type = ? AND legacy_id = ?
                """,
                (source_system, legacy_entity_type, str(legacy_id)),
            )
            row = cur.fetchone()
            return row["canonical_id"] if row else None

    def get_legacy(
        self,
        canonical_entity_type: str,
        canonical_id: str,
    ) -> Optional[Tuple[str, str, str]]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT source_system, legacy_entity_type, legacy_id FROM crosswalk
                WHERE canonical_entity_type = ? AND canonical_id = ?
                """,
                (canonical_entity_type, canonical_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return (row["source_system"], row["legacy_entity_type"], row["legacy_id"])

    def list_by_source(self, source_system: str) -> List[CrosswalkEntry]:
        from datetime import datetime
        with self._cursor() as cur:
            cur.execute("SELECT * FROM crosswalk WHERE source_system = ?", (source_system,))
            rows = cur.fetchall()
        out = []
        for r in rows:
            created = r["created_at"]
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    created = datetime.utcnow()
            out.append(CrosswalkEntry(
                source_system=r["source_system"],
                legacy_entity_type=r["legacy_entity_type"],
                legacy_id=r["legacy_id"],
                canonical_entity_type=r["canonical_entity_type"],
                canonical_id=r["canonical_id"],
                created_at=created,
            ))
        return out

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
