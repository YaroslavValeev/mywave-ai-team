#!/usr/bin/env python3
"""Удалить все миссии (tasks) из БД и опционально почистить артефакты на диске.

Использование (в контейнере app, из корня /app):
  python scripts/clear_all_missions.py --yes
  python scripts/clear_all_missions.py --yes --artifacts

Проекты (projects) и owner_memory* не трогаем.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

# Корень репозитория при локальном запуске
_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

from sqlalchemy import delete, update  # noqa: E402

from app.storage.models import (  # noqa: E402
    Approval,
    AuditEvent,
    Decision,
    ExecutionEvent,
    Handoff,
    MemoryEntry,
    Run,
    Task,
)
from app.storage.repositories import get_session_factory  # noqa: E402


def _artifacts_root() -> Path:
    raw = os.getenv("ARTIFACTS_DIR", "app/artifacts")
    p = Path(raw)
    if not p.is_absolute():
        p = _ROOT / p
    return p


def clear_artifact_files() -> dict[str, int]:
    root = _artifacts_root()
    removed_handoffs = 0
    handoffs = root / "handoffs"
    if handoffs.is_dir():
        for f in handoffs.glob("task_*_step_*.md"):
            try:
                f.unlink()
                removed_handoffs += 1
            except OSError:
                pass
    tasks_dir = root / "tasks"
    had_tasks = tasks_dir.is_dir()
    if had_tasks:
        shutil.rmtree(tasks_dir, ignore_errors=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return {"removed_handoff_md": removed_handoffs, "tasks_dir_reset": int(had_tasks)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Удалить все задачи (миссии) из БД.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Обязательный флаг подтверждения (без него скрипт не выполняется).",
    )
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="Удалить handoffs/*.md с префиксом task_* и сбросить каталог artifacts/tasks/.",
    )
    args = parser.parse_args()
    if not args.yes:
        print("Отказ: укажите --yes для удаления всех миссий.", file=sys.stderr)
        return 2

    Session = get_session_factory()
    with Session() as session:
        n_tasks = session.query(Task).count()
        # Явный порядок: в реальных БД FK на audit_events может быть без CASCADE.
        session.execute(delete(ExecutionEvent))
        session.execute(delete(Approval))
        session.execute(delete(Run))
        session.execute(delete(Decision))
        session.execute(delete(Handoff))
        session.execute(delete(AuditEvent).where(AuditEvent.task_id.isnot(None)))
        session.execute(update(MemoryEntry).values(task_id=None).where(MemoryEntry.task_id.isnot(None)))
        session.execute(delete(Task))
        session.commit()
        deleted = n_tasks

    art: dict[str, int] = {}
    if args.artifacts:
        art = clear_artifact_files()

    print(f"deleted_tasks={deleted}")
    if args.artifacts:
        print(f"artifacts={art!r}")
    print("Рекомендация: перезапустить app (docker compose restart app), чтобы сбросить in-memory runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
