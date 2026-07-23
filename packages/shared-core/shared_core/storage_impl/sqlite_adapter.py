# SQLite implementation of StorageProtocol (ADR-007).
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Optional

from shared_core.protocols import (
    ApprovalRecord,
    ArtifactRecord,
    DecisionRecord,
    EventRecord,
    MemoryRecord,
    ProjectRecord,
    RunRecord,
    TaskRecord,
)


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return dict(zip([c[0] for c in cursor.description], row))


class SQLiteStorage:
    """StorageProtocol implementation using SQLite. One DB file; tables created on first use."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.row_factory = sqlite3.Row
            self._create_tables()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

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

    def _create_tables(self) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                status TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                description TEXT,
                goals TEXT,
                constraints TEXT,
                priority TEXT,
                stage TEXT,
                tags TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                origin_channel TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                task_type TEXT,
                requested_by TEXT,
                assigned_layer TEXT,
                risk_level TEXT,
                approval_required INTEGER,
                parent_task_id TEXT
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                orchestrator TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                executor TEXT,
                attempt INTEGER,
                trace_id TEXT,
                error_summary TEXT
            );
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                reasoning_summary TEXT,
                linked_run_id TEXT,
                requires_owner_approval INTEGER,
                supersedes_decision_id TEXT
            );
            CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                run_id TEXT,
                requested_by TEXT,
                approved_by TEXT,
                approved_at TEXT,
                comment TEXT
            );
            CREATE TABLE IF NOT EXISTS memory (
                memory_id TEXT,
                project_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source TEXT,
                confidence REAL,
                ttl INTEGER,
                linked_task_id TEXT,
                linked_artifact_id TEXT,
                PRIMARY KEY (project_id, scope, key)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                storage_uri TEXT NOT NULL,
                created_at TEXT NOT NULL,
                run_id TEXT,
                checksum TEXT,
                mime_type TEXT,
                title TEXT,
                preview TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                task_id TEXT,
                actor TEXT,
                payload TEXT,
                trace_id TEXT
            );
        """)
        conn.commit()

    def _serialize(self, data: dict) -> dict:
        out = {}
        for k, v in data.items():
            if v is None:
                out[k] = None
            elif isinstance(v, (list, dict)):
                import json
                out[k] = json.dumps(v) if v is not None else None
            else:
                out[k] = v
        return out

    def _dt_str(self, v: Any) -> str:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    # --- TaskRepository ---
    class _TaskRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, task_id: str) -> Optional[TaskRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def create(self, data: dict[str, Any]) -> TaskRecord:
            data = self._outer._serialize(data)
            data["created_at"] = self._outer._dt_str(data["created_at"])
            data["updated_at"] = self._outer._dt_str(data["updated_at"])
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO tasks ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )
            return self.get(data["task_id"])

        def update(self, task_id: str, data: dict[str, Any]) -> Optional[TaskRecord]:
            data = self._outer._serialize(data)
            if "updated_at" in data:
                data["updated_at"] = self._outer._dt_str(data["updated_at"])
            set_clause = ", ".join(f"{k} = ?" for k in data)
            with self._outer._cursor() as cur:
                cur.execute(
                    f"UPDATE tasks SET {set_clause} WHERE task_id = ?",
                    list(data.values()) + [task_id],
                )
                if cur.rowcount == 0:
                    return None
            return self.get(task_id)

        def list_by_project(self, project_id: str, filters: Optional[dict] = None) -> List[TaskRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM tasks WHERE project_id = ?", (project_id,))
                return [dict(r) for r in cur.fetchall()]

    # --- RunRepository ---
    class _RunRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, run_id: str) -> Optional[RunRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def create(self, data: dict[str, Any]) -> RunRecord:
            data = self._outer._serialize(data)
            data["started_at"] = self._outer._dt_str(data["started_at"])
            if data.get("ended_at"):
                data["ended_at"] = self._outer._dt_str(data["ended_at"])
            cols = ", ".join(k for k in data if data[k] is not None)
            vals = [data[k] for k in data if data[k] is not None]
            placeholders = ", ".join("?" * len(vals))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO runs ({cols}) VALUES ({placeholders})",
                    vals,
                )
            return self.get(data["run_id"])

        def update(self, run_id: str, data: dict[str, Any]) -> Optional[RunRecord]:
            data = self._outer._serialize(data)
            if "ended_at" in data and data["ended_at"]:
                data["ended_at"] = self._outer._dt_str(data["ended_at"])
            set_clause = ", ".join(f"{k} = ?" for k in data)
            with self._outer._cursor() as cur:
                cur.execute(
                    f"UPDATE runs SET {set_clause} WHERE run_id = ?",
                    list(data.values()) + [run_id],
                )
                if cur.rowcount == 0:
                    return None
            return self.get(run_id)

        def list_by_task(self, task_id: str) -> List[RunRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM runs WHERE task_id = ?", (task_id,))
                return [dict(r) for r in cur.fetchall()]

    # --- DecisionRepository ---
    class _DecisionRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, decision_id: str) -> Optional[DecisionRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def create(self, data: dict[str, Any]) -> DecisionRecord:
            data = self._outer._serialize(data)
            data["created_at"] = self._outer._dt_str(data["created_at"])
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO decisions ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )
            return self.get(data["decision_id"])

        def list_by_task(self, task_id: str) -> List[DecisionRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM decisions WHERE task_id = ?", (task_id,))
                return [dict(r) for r in cur.fetchall()]

    # --- ApprovalRepository ---
    class _ApprovalRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, approval_id: str) -> Optional[ApprovalRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def create(self, data: dict[str, Any]) -> ApprovalRecord:
            data = self._outer._serialize(data)
            data["requested_at"] = self._outer._dt_str(data["requested_at"])
            if data.get("approved_at"):
                data["approved_at"] = self._outer._dt_str(data["approved_at"])
            cols = ", ".join(k for k in data if data[k] is not None)
            vals = [data[k] for k in data if data[k] is not None]
            placeholders = ", ".join("?" * len(vals))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO approvals ({cols}) VALUES ({placeholders})",
                    vals,
                )
            return self.get(data["approval_id"])

        def update(self, approval_id: str, data: dict[str, Any]) -> Optional[ApprovalRecord]:
            data = self._outer._serialize(data)
            if "approved_at" in data and data["approved_at"]:
                data["approved_at"] = self._outer._dt_str(data["approved_at"])
            set_clause = ", ".join(f"{k} = ?" for k in data)
            with self._outer._cursor() as cur:
                cur.execute(
                    f"UPDATE approvals SET {set_clause} WHERE approval_id = ?",
                    list(data.values()) + [approval_id],
                )
                if cur.rowcount == 0:
                    return None
            return self.get(approval_id)

        def list_by_task(self, task_id: str) -> List[ApprovalRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM approvals WHERE task_id = ?", (task_id,))
                return [dict(r) for r in cur.fetchall()]

    # --- MemoryRepository ---
    class _MemoryRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, project_id: str, scope: str, key: str) -> Optional[MemoryRecord]:
            with self._outer._cursor() as cur:
                cur.execute(
                    "SELECT * FROM memory WHERE project_id = ? AND scope = ? AND key = ?",
                    (project_id, scope, key),
                )
                row = cur.fetchone()
                return dict(row) if row else None

        def upsert(self, data: dict[str, Any]) -> MemoryRecord:
            data = self._outer._serialize(data)
            data["updated_at"] = self._outer._dt_str(data["updated_at"])
            if isinstance(data.get("value"), (dict, list)):
                import json
                data["value"] = json.dumps(data["value"])
            cols = list(data.keys())
            placeholders = ", ".join("?" * len(cols))
            on_conflict = "REPLACE"  # SQLite upsert
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT OR REPLACE INTO memory ({', '.join(cols)}) VALUES ({placeholders})",
                    list(data.values()),
                )
            return self.get(data["project_id"], data["scope"], data["key"])

        def list_by_project(self, project_id: str, scope: Optional[str] = None) -> List[MemoryRecord]:
            with self._outer._cursor() as cur:
                if scope is None:
                    cur.execute("SELECT * FROM memory WHERE project_id = ?", (project_id,))
                else:
                    cur.execute("SELECT * FROM memory WHERE project_id = ? AND scope = ?", (project_id, scope))
                return [dict(r) for r in cur.fetchall()]

    # --- ArtifactRepository ---
    class _ArtifactRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def create(self, data: dict[str, Any]) -> ArtifactRecord:
            data = self._outer._serialize(data)
            data["created_at"] = self._outer._dt_str(data["created_at"])
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO artifacts ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )
            return self.get(data["artifact_id"])

        def list_by_task(self, task_id: str) -> List[ArtifactRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM artifacts WHERE task_id = ?", (task_id,))
                return [dict(r) for r in cur.fetchall()]

    # --- EventRepository ---
    class _EventRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, event_id: str) -> Optional[EventRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def append(self, data: dict[str, Any]) -> EventRecord:
            data = self._outer._serialize(data)
            data["timestamp"] = self._outer._dt_str(data["timestamp"])
            if isinstance(data.get("payload"), dict):
                import json
                data["payload"] = json.dumps(data["payload"])
            cols = ", ".join(k for k in data if data[k] is not None)
            vals = [data[k] for k in data if data[k] is not None]
            placeholders = ", ".join("?" * len(vals))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO events ({cols}) VALUES ({placeholders})",
                    vals,
                )
            return self.get(data["event_id"])

        def list_by_run(self, run_id: str) -> List[EventRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM events WHERE run_id = ? ORDER BY timestamp", (run_id,))
                return [dict(r) for r in cur.fetchall()]

    # --- ProjectRepository ---
    class _ProjectRepo:
        def __init__(self, outer: SQLiteStorage) -> None:
            self._outer = outer

        def get(self, project_id: str) -> Optional[ProjectRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
                row = cur.fetchone()
                return dict(row) if row else None

        def create(self, data: dict[str, Any]) -> ProjectRecord:
            data = self._outer._serialize(data)
            data["created_at"] = self._outer._dt_str(data["created_at"])
            data["updated_at"] = self._outer._dt_str(data["updated_at"])
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            with self._outer._cursor() as cur:
                cur.execute(
                    f"INSERT INTO projects ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )
            return self.get(data["project_id"])

        def update(self, project_id: str, data: dict[str, Any]) -> Optional[ProjectRecord]:
            data = self._outer._serialize(data)
            if "updated_at" in data:
                data["updated_at"] = self._outer._dt_str(data["updated_at"])
            set_clause = ", ".join(f"{k} = ?" for k in data)
            with self._outer._cursor() as cur:
                cur.execute(
                    f"UPDATE projects SET {set_clause} WHERE project_id = ?",
                    list(data.values()) + [project_id],
                )
                if cur.rowcount == 0:
                    return None
            return self.get(project_id)

        def list_all(self) -> List[ProjectRecord]:
            with self._outer._cursor() as cur:
                cur.execute("SELECT * FROM projects ORDER BY created_at")
                return [dict(r) for r in cur.fetchall()]

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._tasks = SQLiteStorage._TaskRepo(self)
        self._runs = SQLiteStorage._RunRepo(self)
        self._decisions = SQLiteStorage._DecisionRepo(self)
        self._approvals = SQLiteStorage._ApprovalRepo(self)
        self._memory = SQLiteStorage._MemoryRepo(self)
        self._artifacts = SQLiteStorage._ArtifactRepo(self)
        self._events = SQLiteStorage._EventRepo(self)
        self._projects = SQLiteStorage._ProjectRepo(self)

    @property
    def tasks(self) -> _TaskRepo:
        return self._tasks

    @property
    def runs(self) -> _RunRepo:
        return self._runs

    @property
    def decisions(self) -> _DecisionRepo:
        return self._decisions

    @property
    def approvals(self) -> _ApprovalRepo:
        return self._approvals

    @property
    def memory(self) -> _MemoryRepo:
        return self._memory

    @property
    def artifacts(self) -> _ArtifactRepo:
        return self._artifacts

    @property
    def events(self) -> _EventRepo:
        return self._events

    @property
    def projects(self) -> _ProjectRepo:
        return self._projects
