"""Bind owner consent to the exact repository, revision and patch reviewed."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def latest_decision(task):
    return max(task.decisions, key=lambda decision: decision.id, default=None)


def _snapshot(request):
    from app.execution.service import ExecutionRequestError

    workspace = Path(request["workspace_path"])
    try:
        def git(*args):
            result = subprocess.run(
                ["git", *args], cwd=workspace, capture_output=True,
                text=True, timeout=15, check=True,
            )
            return result.stdout.strip()

        patch = Path(request["patch_path"]).read_bytes()
        snapshot = {
            **request,
            "repository_path": str(Path(git("rev-parse", "--show-toplevel")).resolve()),
            "git_directory": str(Path(git("rev-parse", "--absolute-git-dir")).resolve()),
            "base_sha": git("rev-parse", "HEAD"),
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
            "executor": "code_pr",
            "mode": "patch",
        }
        return snapshot, patch
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExecutionRequestError("Cannot bind execution approval to repository and patch.") from exc


def record_bound_approval(repo, task):
    """Record normal consent unchanged; code requests require a valid snapshot."""
    from app.execution.service import _validated_request

    payload = task.business_action_json or {}
    request = payload.get("execution_request") if isinstance(payload, dict) else None
    snapshot = None
    if isinstance(request, dict):
        snapshot, _ = _snapshot(_validated_request(task))
    # Keep a trusted copy on the decision: the general audit API accepts events.
    rationale = json.dumps({"execution_approval": snapshot}, sort_keys=True) if snapshot else None
    decision = repo.add_decision(task.id, decision="a", owner_approval=True, rationale=rationale)
    if snapshot:
        repo.add_audit_event(
            "EXECUTION_APPROVAL_BOUND", task_id=task.id,
            payload={"decision_id": decision.id, **snapshot},
        )
    return decision


def validated_approved_patch(task, request):
    from app.execution.service import ExecutionRequestError

    decision = latest_decision(task)
    if not decision or not decision.owner_approval or decision.decision.lower() not in {"a", "approve"}:
        raise ExecutionRequestError("A fresh Owner approve is required for execution.")
    try:
        approved = json.loads(decision.rationale or "{}").get("execution_approval")
    except (ValueError, AttributeError):
        approved = None
    current, patch = _snapshot(request)
    if not approved or approved != current:
        raise ExecutionRequestError("Execution patch, repository or base revision changed; new Owner approve required.")
    return patch
