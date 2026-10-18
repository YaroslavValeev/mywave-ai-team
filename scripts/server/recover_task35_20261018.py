"""Recover one confirmed orphan; never complete a business task or start a run."""

import argparse
import inspect
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path


def needs_recovery(snapshot, now):
    if (
        snapshot.get("task_id") != 35
        or snapshot.get("created_at") != "2026-10-01T12:34:03.124363"
    ):
        raise RuntimeError("Unexpected mission identity; left untouched")
    if (
        snapshot.get("runtime_active") is not False
        or snapshot.get("persisted_run_active") is not False
    ):
        raise RuntimeError("Active run; mission left untouched")
    if snapshot.get("status") == "REWORK":
        return False
    if snapshot.get("status") != "IN_PIPELINE":
        raise RuntimeError("Unexpected status; mission left untouched")
    if not snapshot.get("updated_at") or now - datetime.fromisoformat(
        snapshot["updated_at"]
    ) < timedelta(days=1):
        raise RuntimeError("Mission is not stale; left untouched")
    return True


WORKER = r"""
import json,os,sys,urllib.request
from datetime import datetime,timedelta
from sqlalchemy import select
from app.storage.models import Task,Run,AuditEvent
from app.storage.repositories import get_session_factory
POLICY_SOURCE
execute=sys.argv[1]=='execute'
request=urllib.request.Request('http://127.0.0.1:8080/api/tasks/35/runtime',headers={'X-API-Key':os.environ['OWNER_API_KEY']})
with urllib.request.urlopen(request,timeout=30) as response:runner=json.load(response)['runner']
with get_session_factory()() as session:
    query=select(Task).where(Task.id==35)
    if execute:query=query.with_for_update()
    task=session.execute(query).scalar_one()
    active=session.execute(select(Run.id).where(Run.task_id==35,Run.is_active.is_(True))).first() is not None
    before={'task_id':35,'status':task.status,'created_at':task.created_at.isoformat(),
            'updated_at':task.updated_at.isoformat() if task.updated_at else None,
            'runtime_active':runner.get('is_active',True),'persisted_run_active':active}
    recover=needs_recovery(before,datetime.utcnow())
    result={'task_id':35,'mode':'execute' if execute else 'check','changed':False,'before':before,'would_recover':recover}
    if recover and execute:
        task.status='REWORK'
        task.updated_at=datetime.utcnow()
        event=AuditEvent(event_type='runtime_orphan_recovered',task_id=35,
            payload_json={'status_before':'IN_PIPELINE','status_after':'REWORK',
                     'reason':'Stale task, idle application runtime, no active persisted run; owner-authorized runtime recovery. Original content preserved.',
                     'source':'owner_authorized_runtime_recovery','business_outcome_verified':False})
        session.add(event)
        session.commit()
        result.update(changed=True,status='REWORK',audit_event_id=event.id,summary_preserved=True,business_outcome_declared=False)
    else:result['status']=task.status
    print(json.dumps(result,indent=2))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-approved-task", type=int)
    args = parser.parse_args()
    if args.execute and args.owner_approved_task != 35:
        parser.error("Execution requires --owner-approved-task 35")
    os.umask(0o077)
    code = WORKER.replace("POLICY_SOURCE", inspect.getsource(needs_recovery))
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "ai-team-app-1",
            "python",
            "-",
            "execute" if args.execute else "check",
        ],
        input=code.encode(),
        capture_output=True,
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError("Recovery blocked; no completion or approval was granted")
    proof = json.loads(result.stdout)
    path = Path("/opt/mywave/ai-team-runtime/task35-runtime-recovery-20261018.json")
    if args.execute and (proof.get("changed") or not path.exists()):
        path.write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
