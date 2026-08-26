from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from app.orchestrator.runtime import OrchestrationCancelled, get_orchestration_runtime
from app.runners.cursor_runner.pr_loop import run_pr_loop
from app.shared.audit import log_audit
from app.storage.repositories import TaskRepository, get_session_factory


class ExecutionRequestError(ValueError):
    pass


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _allowed_roots() -> tuple[Path, ...]:
    raw_json = (os.getenv("EXECUTION_ALLOWED_ROOTS_JSON") or "").strip()
    values: list[str]
    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ExecutionRequestError("EXECUTION_ALLOWED_ROOTS_JSON is invalid") from exc
        values = parsed if isinstance(parsed, list) else []
    else:
        values = [value for value in (os.getenv("EXECUTION_ALLOWED_ROOTS") or "").split(os.pathsep) if value]
    return tuple(Path(value).expanduser().resolve() for value in values if isinstance(value, str) and value.strip())


def _validated_request(task: Any) -> dict[str, str]:
    payload = task.business_action_json if isinstance(task.business_action_json, dict) else {}
    request = payload.get("execution_request")
    if not isinstance(request, dict):
        raise ExecutionRequestError("Для миссии не подготовлен execution_request.")
    if request.get("executor") != "code_pr" or request.get("mode") != "patch":
        raise ExecutionRequestError("Разрешён только executor=code_pr с mode=patch.")

    roots = _allowed_roots()
    if not roots:
        raise ExecutionRequestError("EXECUTION_ALLOWED_ROOTS не настроен; исполнение заблокировано.")
    workspace_value = str(request.get("workspace_path") or "").strip()
    patch_value = str(request.get("patch_path") or "").strip()
    if not workspace_value or not patch_value:
        raise ExecutionRequestError("execution_request должен содержать workspace_path и patch_path.")
    workspace = Path(workspace_value).expanduser().resolve()
    if not workspace.is_dir() or not any(_is_relative_to(workspace, root) for root in roots):
        raise ExecutionRequestError("Workspace отсутствует или находится вне разрешённых корней.")

    artifacts_root = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts")).expanduser().resolve()
    patch_path = Path(patch_value).expanduser().resolve()
    if patch_path.suffix.lower() not in {".patch", ".diff"}:
        raise ExecutionRequestError("Execution artifact должен быть файлом .patch или .diff.")
    if not patch_path.is_file() or not _is_relative_to(patch_path, artifacts_root):
        raise ExecutionRequestError("Patch отсутствует или находится вне ARTIFACTS_DIR.")

    return {"workspace_path": str(workspace), "patch_path": str(patch_path)}


def _has_owner_approval(task: Any) -> bool:
    return any(
        bool(decision.owner_approval) and str(decision.decision).lower() in {"a", "approve"}
        for decision in task.decisions
    )


def execution_capabilities(task: Any, runner: dict | None = None) -> dict[str, Any]:
    active = bool((runner or {}).get("is_active"))
    try:
        _validated_request(task)
        configured = True
        reason = "Owner approve получен. Можно запустить code -> tests -> PR."
    except ExecutionRequestError as exc:
        configured = False
        reason = str(exc)
    approved = _has_owner_approval(task)
    can_start = task.status in {"EXECUTION_READY", "EXECUTION_FAILED"} and approved and configured and not active
    if active:
        reason = "Для миссии уже выполняется фоновый процесс."
    elif not approved:
        reason = "Сначала требуется явный Owner approve."
    elif task.status not in {"EXECUTION_READY", "EXECUTION_FAILED"}:
        reason = "Исполнение доступно только в статусе EXECUTION_READY или после исправления ошибки."
    return {"can_start": can_start, "configured": configured, "approved": approved, "reason": reason}


def _apply_patch(workspace_path: str, patch_path: str, cancel_check) -> None:
    cancel_check()
    for command in (
        ["git", "apply", "--check", patch_path],
        ["git", "apply", "--whitespace=error", patch_path],
    ):
        result = subprocess.run(
            command,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise ExecutionRequestError((result.stderr or result.stdout or "git apply failed").strip())
        cancel_check()


def _record_terminal_failure(task_id: int, message: str, *, cancelled: bool = False) -> None:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        status = "EXECUTION_READY" if cancelled else "EXECUTION_FAILED"
        repo.update_task(task_id, status=status, summary=message)
        repo.add_execution_event(
            task_id,
            run_db_id=None,
            event_type="execution_cancelled" if cancelled else "execution_failed",
            phase="execution",
            payload={"message": message, "status_after": status},
        )
        log_audit(
            repo,
            "execution_cancelled" if cancelled else "execution_failed",
            task_id=task_id,
            payload={"note": message, "status_after": status},
        )


def start_approved_execution(task_id: int) -> dict[str, Any]:
    runtime = get_orchestration_runtime()
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise ExecutionRequestError("Миссия не найдена.")
        capabilities = execution_capabilities(task, runtime.snapshot(task_id))
        if not capabilities["can_start"]:
            raise ExecutionRequestError(capabilities["reason"])
        request = _validated_request(task)
        task_data = {"id": task.id, "summary": task.summary or ""}
        repo.update_task(task_id, status="EXECUTING", summary="Команда применяет утверждённый patch в изолированной git-ветке.")
        log_audit(
            repo,
            "execution_started",
            task_id=task_id,
            payload={"executor": "code_pr", "mode": "patch", "status_after": "EXECUTING"},
        )

    branch_name = f"execution/task-{task_id}-{uuid.uuid4().hex[:8]}"

    def target(control) -> dict:
        try:
            control.set_phase("execution", message="Применяю утверждённый patch.", current_step="DEV")
            result = asyncio.run(
                run_pr_loop(
                    task_id,
                    request["workspace_path"],
                    apply_callback=lambda workspace, _: _apply_patch(
                        workspace, request["patch_path"], control.check_cancelled
                    ),
                    mode="patch",
                    task_data_override=task_data,
                    task_update_callback=lambda *args, **kwargs: None,
                    cancel_check=control.check_cancelled,
                    branch_name=branch_name,
                )
            )
            control.check_cancelled()
            if not result.get("success"):
                message = str(result.get("error") or "Исполнение завершилось ошибкой.")
                _record_terminal_failure(task_id, message)
                raise RuntimeError(message)

            control.set_phase("validation", message="Тесты прошли; фиксирую evidence и PR.", current_step="QA")
            with Session() as session:
                repo = TaskRepository(session)
                repo.update_task(
                    task_id,
                    status="APPROVED_WAIT_MERGE",
                    summary="Patch применён, тесты прошли, PR создан. Требуется ручной merge владельца.",
                    pr_url=result.get("pr_url") or "",
                    commit_sha=result.get("commit_sha") or "",
                    ci_url=result.get("ci_url") or "",
                )
                repo.add_execution_event(
                    task_id,
                    run_db_id=None,
                    event_type="validation_done",
                    phase="validation",
                    payload={**result, "status_after": "APPROVED_WAIT_MERGE"},
                )
                log_audit(
                    repo,
                    "validation_done",
                    task_id=task_id,
                    payload={"note": "Тесты прошли, PR создан.", "status_after": "APPROVED_WAIT_MERGE"},
                )
            return {"status": "APPROVED_WAIT_MERGE", "summary": "Исполнение и локальная проверка завершены; PR ожидает merge."}
        except OrchestrationCancelled:
            _record_terminal_failure(task_id, "Исполнение остановлено владельцем на безопасной checkpoint-точке.", cancelled=True)
            raise

    try:
        runner = runtime.start(task_id, source="owner_approved_execution", target=target)
    except Exception:
        _record_terminal_failure(task_id, "Не удалось запустить фоновый execution job.")
        raise
    return {"ok": True, "task_id": task_id, "status": "EXECUTING", "runner": runner}
