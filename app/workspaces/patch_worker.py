"""Bounded trusted-host worker. Web app never receives a Docker socket.

Run from a dedicated worker environment with database access and the explicitly
registered project profiles. --once processes at most one queued job. Interrupted
claimed jobs require owner recovery; they are never silently replayed.
"""

import argparse
import json
import os

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.storage.models import Run, Task
from app.storage.repositories import get_engine
from app.workspaces.access import Scope
from app.workspaces.patch_executor import (
    ExecutionConflict,
    PROFILE_ENV,
    profiles,
    require,
    run_job,
)


def run_once():
    require(
        os.getenv("WORKSPACE_PATCH_WORKER_ENABLED") == "true"
        and bool(os.getenv("DATABASE_URL")),
        "Explicit worker activation and database URL required",
    )
    profiles(
        Scope("worker:configuration", 1, 1)
    )  # Validate all configured profiles before SQL selection.
    configured = json.loads(os.getenv(PROFILE_ENV, "[]"))
    if not configured:
        return {"processed": False}
    predicates = [
        and_(
            Task.workspace_id == p["workspace_id"],
            Task.project_id == p["project_id"],
            Run.current_step == p["id"],
        )
        for p in configured
    ]
    with Session(get_engine()) as session:
        rows = session.execute(
            select(Run, Task)
            .join(Task, Task.id == Run.task_id)
            .where(
                Run.orchestrator == "scoped_patch_v1",
                Run.is_active.is_(True),
                Run.state == "running",
                Run.phase == "queued",
                Task.status == "EXECUTING",
                Task.workspace_id.is_not(None),
                Task.project_id.is_not(None),
                or_(*predicates),
            )
            .order_by(Run.id)
            .limit(100)
        )
        for run, task in rows:
            binding = json.loads(run.message)
            scope = Scope(binding["principal_id"], task.workspace_id, task.project_id)
            try:
                values = profiles(scope)
            except ExecutionConflict:
                continue
            if not values:
                continue
            changed = session.execute(
                update(Run)
                .where(Run.id == run.id, Run.phase == "queued", Run.is_active.is_(True))
                .values(phase="claimed")
            )
            if changed.rowcount != 1:
                session.rollback()
                continue
            run_id, task_id = run.run_id, task.id
            sha = json.loads(run.message)["proposal_sha256"]
            session.commit()
            break
        else:
            return {"processed": False}
    run_job(scope, task_id, run_id, sha)
    with Session(get_engine()) as session:
        state = session.scalar(select(Run.state).where(Run.run_id == run_id))
    return {"processed": True, "task_id": task_id, "run_id": run_id, "state": state}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    result = run_once()
    print(json.dumps(result))
    if result.get("state") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
