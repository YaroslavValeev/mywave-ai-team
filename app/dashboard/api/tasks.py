# app/dashboard/api/tasks.py — /tasks*, /missions*, /artifacts* routes.

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import DBAPIError

from app.dashboard.api.common import (
    ATTACHMENT_DOCUMENT_ROLE,
    ATTACHMENT_STEP_NAME,
    CHAT_EVENT_TYPES,
    CHAT_QUICK_PROMPTS,
    STATUS_SCENES,
    TASK_LIVE_POLL_INTERVAL_MS,
    _attachment_summary_lines,
    _build_control_state,
    _build_owner_actions,
    _build_task_timeline,
    _build_unified_mission_thread,
    _chat_reply_texts,
    _chat_speaker,
    _decode_attachment_body,
    _event_status_after,
    _last_live_event_id,
    _list_chat_messages,
    _max_handoff_step_index,
    _mission_thread_payload,
    _persona_for_step,
    _query_audit_events,
    _runner_snapshot,
    _safe_payload,
    _safe_text,
    _start_action_reason,
    _start_background_orchestration,
    _stop_action_reason,
    _task_can_chat,
    _task_can_start_background,
    _task_upload_dir,
    _unified_mission_bundle,
    _unique_upload_path,
    _write_owner_rework_document,
    apply_merge_confirmation,
    apply_owner_decision,
    build_task_documents,
    execution_event_to_public_dict,
    get_session_factory,
    latest_verdict_handoff,
    list_regular_handoffs,
    log_audit,
    log_decision,
    logger,
    preview_document_bytes,
    read_task_document,
    redact,
    require_owner_key,
    run_task_orchestration,
    run_to_public_dict,
    run_triage,
    scrub_secrets,
    AuditEvent,
    get_orchestration_runtime,
    TaskRepository,
)

router = APIRouter()


@router.get("/tasks")
async def api_list_tasks():
    """Список задач."""
    try:
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            tasks = repo.get_all_tasks()
            return [
                {
                    "id": t.id,
                    "mission_id": t.id,
                    "domain": t.domain,
                    "status": t.status,
                    "criticality": t.criticality,
                    "business_type": t.business_type,
                    "impact_level": t.impact_level,
                    "impact_score": t.impact_score,
                    "pr_url": t.pr_url,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "runner": _runner_snapshot(t.id),
                }
                for t in tasks
            ]
    except DBAPIError as exc:
        logger.exception("api_list_tasks: database error")
        raise HTTPException(
            status_code=500,
            detail=(
                "Ошибка БД при чтении списка задач (схема PostgreSQL не совпадает с кодом). "
                "Если база уже была с данными: из каталога с docker-compose выполни "
                "docker compose run --rm --no-deps --entrypoint sh app "
                "-c \"alembic stamp 001 && alembic upgrade head\" "
                "затем docker compose up -d --force-recreate app. "
                "Если образ/код старые — сначала docker compose build app. "
                "Для пустой БД обычно хватает: docker compose exec app alembic upgrade head."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("api_list_tasks: unexpected error")
        raise HTTPException(status_code=500, detail="Не удалось получить список задач.") from exc


@router.post("/tasks")
async def api_create_task(request: Request):
    """Создать задачу. Body: {owner_text} или {domain, task_type, payload, criticality}."""
    body = await request.json() or {}
    owner_text = body.get("owner_text")
    if not owner_text:
        domain = body.get("domain", "PRODUCT_DEV")
        task_type = body.get("task_type", "general")
        payload = body.get("payload", {})
        owner_text = f"#TASK Domain: {domain}, Type: {task_type}. Payload: {payload}"
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text=owner_text)
        if body.get("business_type") or body.get("business_action") or body.get("business_unit"):
            impact_level = body.get("impact_level")
            impact_score = body.get("impact_score")
            try:
                impact_score = float(impact_score) if impact_score is not None else None
            except (TypeError, ValueError):
                impact_score = None
            ba: dict = {}
            raw_ba = body.get("business_action")
            if isinstance(raw_ba, dict):
                ba.update(raw_ba)
            for key in ("business_unit", "business_goal_hint", "intake_title"):
                val = body.get(key)
                if val:
                    ba[str(key)] = val
            task = repo.update_task(
                task.id,
                business_type=(body.get("business_type") or None),
                impact_level=(impact_level or None),
                impact_score=impact_score,
                business_action_json=ba if ba else None,
                business_outcome=(body.get("business_outcome") or None),
            ) or task
        log_audit(
            repo,
            "task_created",
            task_id=task.id,
            payload={"source": "api", "status_after": "NEW", "mission_id": task.id},
        )
        if body.get("domain"):
            triage_result = run_triage(owner_text)
            task = repo.update_task(
                task.id,
                domain=triage_result.get("domain"),
                task_type=triage_result.get("task_type"),
                criticality=triage_result.get("criticality"),
                plan_or_execute=triage_result.get("plan_or_execute"),
            )
        return {
            "id": task.id,
            "mission_id": task.id,
            "status": task.status,
            "domain": task.domain,
            "mission": _unified_mission_bundle(task.id),
        }


@router.get("/tasks/{task_id}")
async def api_get_task(task_id: int, raw: int = 0, _=Depends(require_owner_key)):
    """Детали задачи."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        owner_text_raw = task.owner_text or ""
        allow_pii = "ALLOW_PII" in owner_text_raw
        if raw == 1 and allow_pii:
            owner_text_display = scrub_secrets(owner_text_raw)
        else:
            owner_text_display = redact(owner_text_raw)
        verdict_handoff = latest_verdict_handoff(task)
        return {
            "id": task.id,
            "mission_id": task.id,
            "project_id": task.project_id,
            "owner_text": owner_text_display,
            "status": task.status,
            "domain": task.domain,
            "task_type": task.task_type,
            "business_type": task.business_type,
            "impact_level": task.impact_level,
            "impact_score": task.impact_score,
            "business_action": task.business_action_json,
            "business_outcome": task.business_outcome,
            "criticality": task.criticality,
            "report_path": task.report_path,
            "summary": redact(task.summary or ""),
            "pr_url": task.pr_url,
            "commit_sha": task.commit_sha,
            "ci_url": task.ci_url,
            "verdict_path": verdict_handoff.md_path if verdict_handoff else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "decisions": [{"decision": d.decision, "owner_approval": d.owner_approval} for d in task.decisions],
            "handoffs": [{"id": h.id, "step_name": h.step_name, "md_path": h.md_path} for h in list_regular_handoffs(task)],
            "documents": build_task_documents(task),
            "mission": _unified_mission_bundle(task.id),
        }


@router.get("/missions/{mission_id}/scene")
async def api_get_mission_scene(mission_id: int):
    """Алиас продукта: mission == task; тот же unified thread, что у /api/tasks/{id}/scene."""
    return await api_get_task_scene(mission_id)


@router.get("/missions/{mission_id}/thread")
async def api_get_mission_thread(
    mission_id: int,
    limit: int = Query(200, ge=1, le=500),
):
    """Полная единая нить: audit + чат + handoffs (хронология для dual-entry)."""
    return _mission_thread_payload(mission_id, limit)


@router.get("/tasks/{task_id}/thread")
async def api_get_task_thread(
    task_id: int,
    limit: int = Query(200, ge=1, le=500),
):
    return _mission_thread_payload(task_id, limit)


@router.get("/tasks/{task_id}/scene")
async def api_get_task_scene(task_id: int):
    """Обогащённая модель задачи для game UI."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        log_rows = _query_audit_events(session, task_id=task_id, include_api_requests=True).order_by(AuditEvent.created_at).all()
        logs = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "payload": _safe_payload(event.payload_json),
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "status_after": _event_status_after(event.event_type, _safe_payload(event.payload_json)),
            }
            for event in log_rows
        ]
        scene = STATUS_SCENES.get(
            task.status,
            {"title": "Рабочая сцена", "subtitle": "Система обрабатывает задачу.", "zone": "worklane", "animation": "think"},
        )
        runner = _runner_snapshot(task_id)
        owner_actions = _build_owner_actions(task, runner)
        control_state = _build_control_state(task, runner, owner_actions)
        chat_messages = _list_chat_messages(session, task_id)
        documents = build_task_documents(task)
        handoffs = []
        for handoff in list_regular_handoffs(task):
            payload = handoff.payload_json or {}
            handoffs.append(
                {
                    "id": handoff.id,
                    "step_index": handoff.step_index,
                    "step_name": handoff.step_name,
                    "created_at": handoff.created_at.isoformat() if handoff.created_at else None,
                    "md_path": handoff.md_path,
                    "artifact_url": f"/api/artifacts/{handoff.id}?task_id={task.id}",
                    "payload": payload,
                    "persona": _persona_for_step(handoff.step_name),
                }
            )
        current_actor = handoffs[-1]["persona"] if handoffs else _persona_for_step("COORDINATOR")
        return {
            "mission": _unified_mission_bundle(task.id),
            "task": {
                "id": task.id,
                "status": task.status,
                "domain": task.domain,
                "task_type": task.task_type,
                "criticality": task.criticality,
                "plan_or_execute": task.plan_or_execute,
                "owner_text": redact(task.owner_text or ""),
                "summary": redact(task.summary or ""),
                "report_path": task.report_path,
                "pr_url": task.pr_url,
                "commit_sha": task.commit_sha,
                "ci_url": task.ci_url,
                "risk_table": task.risk_table_json or [],
                "rework_cycles": task.rework_cycles or 0,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            },
            "scene": scene,
            "current_actor": current_actor,
            "cast": [_persona_for_step(code) for code in ["COORDINATOR", "PS", "PM", "UX", "FE", "BE", "ARCH", "QA", "DEVOPS", "RC", "SEC", "LEGAL", "FIN", "JUDGE", "OWNER"]],
            "handoffs": handoffs,
            "decisions": [
                {
                    "decision": d.decision,
                    "rationale": redact(d.rationale or ""),
                    "owner_approval": d.owner_approval,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in task.decisions
            ],
            "documents": documents,
            "timeline": _build_task_timeline(task, logs),
            "logs": logs,
            "live": {
                "last_event_id": _last_live_event_id(session, task_id=task_id),
                "poll_interval_ms": TASK_LIVE_POLL_INTERVAL_MS,
                "has_open_pr": bool(task.pr_url),
                "can_auto_refresh": runner.get("is_active", False) or task.status not in {"DONE", "ARCHIVED"},
            },
            "runner": {
                **runner,
                "can_start": _task_can_start_background(task) and not runner.get("is_active", False),
                "start_reason": _start_action_reason(task, runner),
                "stop_reason": _stop_action_reason(task, runner),
            },
            "chat": {
                "messages": chat_messages,
                "can_send": _task_can_chat(task),
                "quick_prompts": CHAT_QUICK_PROMPTS,
            },
            "owner_actions": owner_actions,
            "control_state": control_state,
        }


@router.get("/tasks/{task_id}/documents")
async def api_list_task_documents(task_id: int):
    """Список task-level документов: verdict, report, handoffs."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"documents": build_task_documents(task)}


@router.post("/tasks/{task_id}/attachments/upload")
async def api_upload_task_attachments(task_id: int, request: Request):
    """Добавить входные файлы миссии (.md/.txt/.docx) как документы, доступные команде."""
    body = await request.json() or {}
    files = body.get("files") or []
    if not isinstance(files, list) or not files:
        raise HTTPException(status_code=400, detail="Нужен непустой список files")

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        upload_dir = _task_upload_dir(task_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        next_index = _max_handoff_step_index(task) + 1
        uploaded = []

        for offset, file_body in enumerate(files):
            file_name, raw_bytes = _decode_attachment_body(file_body)
            path = _unique_upload_path(upload_dir, file_name)
            path.write_bytes(raw_bytes)
            preview_excerpt = preview_document_bytes(file_name, raw_bytes)
            payload = {
                "document_role": ATTACHMENT_DOCUMENT_ROLE,
                "document_title": file_name,
                "document_subtitle": "Входной файл миссии",
                "original_name": file_name,
                "file_suffix": path.suffix.lower(),
                "file_size": len(raw_bytes),
                "preview_excerpt": preview_excerpt,
                "summary": _attachment_summary_lines(file_name, preview_excerpt),
                "next_action": "Учитывать этот файл как входной контекст в следующих handoff и итоговых документах.",
            }
            repo.add_handoff(
                task_id=task_id,
                step_index=next_index + offset,
                step_name=ATTACHMENT_STEP_NAME,
                payload=payload,
                md_path=str(path),
            )
            log_audit(
                repo,
                "task_file_uploaded",
                task_id=task_id,
                payload={"file_name": file_name, "file_count": len(files), "status_after": task.status},
            )
            uploaded.append(
                {
                    "name": file_name,
                    "path": str(path),
                    "size": len(raw_bytes),
                    "preview_excerpt": preview_excerpt,
                }
            )

        refreshed = repo.get_task(task_id)
        return {"ok": True, "uploaded": uploaded, "documents": build_task_documents(refreshed)}


@router.get("/tasks/{task_id}/documents/{document_key}")
async def api_get_task_document(task_id: int, document_key: str):
    """Содержимое task-level документа: verdict, report или artifact-N."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        document = read_task_document(task, document_key)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document


@router.patch("/tasks/{task_id}")
async def api_update_task(task_id: int, request: Request):
    """Обновить задачу. Body: {status, pr_url, commit_sha, ci_url, summary, ...}."""
    body = await request.json() or {}
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        allowed = {"status", "pr_url", "commit_sha", "ci_url", "summary", "report_path"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if not updates:
            return {"id": task_id, "status": task.status}
        task = repo.update_task(task_id, **updates)
        if "pr_url" in updates and updates.get("pr_url"):
            import os
            from app.bot.notify import notify_pr_ready

            dash_url = os.getenv("DASHBOARD_URL", "https://agm.mywavetreaning.ru")
            asyncio.create_task(notify_pr_ready(task_id, updates["pr_url"], task.summary or "", dash_url))
        return {"id": task.id, "status": task.status}


@router.get("/tasks/{task_id}/artifacts")
async def api_list_artifacts(task_id: int):
    """Список артефактов (handoffs) по задаче."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        artifacts = [
            {"id": h.id, "step_index": h.step_index, "step_name": h.step_name, "md_path": h.md_path}
            for h in list_regular_handoffs(task)
        ]
        return {"artifacts": artifacts}


@router.get("/artifacts/{artifact_id}")
async def api_get_artifact(artifact_id: int, task_id: int):
    """Содержимое артефакта (handoff md)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        handoff = next((h for h in task.handoffs if h.id == artifact_id), None)
        if not handoff or not handoff.md_path:
            raise HTTPException(status_code=404, detail="Artifact not found")
        path = Path(handoff.md_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Artifact file not found")
        content = path.read_text(encoding="utf-8")
        return {"content": redact(content)}


@router.post("/tasks/{task_id}/pipeline/run")
async def api_run_pipeline(task_id: int):
    """Запустить pipeline (triage -> pipeline -> roundtable -> court)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return run_task_orchestration(repo, task_id, source="api")


@router.post("/tasks/{task_id}/pipeline/start")
async def api_start_pipeline_background(task_id: int):
    """Запустить AI-Team в фоне, чтобы его можно было остановить из Office UI."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        runner_snapshot = _runner_snapshot(task_id)
        if not (_task_can_start_background(task) and not runner_snapshot.get("is_active", False)):
            raise HTTPException(status_code=409, detail=_start_action_reason(task, runner_snapshot))
        try:
            runner = _start_background_orchestration(task_id, source="office_background")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_audit(
            repo,
            "pipeline_background_started",
            task_id=task_id,
            payload={"source": "office_background", "status_after": task.status},
        )
        return {"ok": True, "task_id": task_id, "runner": runner}


@router.post("/tasks/{task_id}/pipeline/stop")
async def api_stop_pipeline_background(task_id: int):
    """Запросить безопасную остановку фонового AI-Team job-а."""
    runtime = get_orchestration_runtime()
    try:
        runner = runtime.request_stop(task_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "task_id": task_id, "runner": runner}


@router.get("/tasks/{task_id}/runtime")
async def api_get_task_runtime(task_id: int):
    """Текущее состояние фонового AI-Team job-а."""
    return {"runner": _runner_snapshot(task_id)}


@router.get("/tasks/{task_id}/runs")
async def api_list_task_runs(task_id: int):
    """Персистентные проходы оркестрации (SoT run_id) для задачи."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        runs = repo.list_runs_for_task(task_id)
        return {
            "task_id": task_id,
            "runs": [run_to_public_dict(r) for r in runs],
        }


@router.get("/tasks/{task_id}/execution-events")
async def api_list_task_execution_events(task_id: int, limit: int = Query(100, ge=1, le=500)):
    """События исполнения (SoT) по задаче: run_started, run_completed, …"""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        events = repo.list_execution_events_for_task(task_id, limit=limit)
        return {
            "task_id": task_id,
            "events": [execution_event_to_public_dict(e) for e in events],
        }


@router.post("/tasks/{task_id}/rework/start")
async def api_rework_task_background(task_id: int):
    """Owner rework + запуск нового фонового прохода без блокировки UI."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        runner_snapshot = _runner_snapshot(task_id)
        owner_actions = _build_owner_actions(task, runner_snapshot)
        if not owner_actions["can_rework"]:
            raise HTTPException(status_code=409, detail=owner_actions["rework_reason"])
        log_decision(repo, task_id, decision="r", owner_approval=False)
        repo.update_task(
            task_id,
            status="REWORK",
            summary="Owner отправил задачу на доработку. Новый проход AI-Team запущен в фоне и может быть остановлен вручную.",
        )
        _write_owner_rework_document(repo, repo.get_task(task_id))
        log_audit(
            repo,
            "OWNER_REWORK",
            task_id=task_id,
            payload={"decision": "rework", "source": "office_background", "status_after": "REWORK"},
        )
        try:
            runner = _start_background_orchestration(task_id, source="rework_background")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_audit(
            repo,
            "pipeline_background_started",
            task_id=task_id,
            payload={"source": "rework_background", "status_after": "REWORK"},
        )
        return {"ok": True, "task_id": task_id, "runner": runner, "status": "REWORK"}


@router.post("/tasks/{task_id}/chat")
async def api_chat_with_team(task_id: int, request: Request):
    """Отправить сообщение команде по миссии и получить короткий русский ответ."""
    body = await request.json() or {}
    message = _safe_text(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        log_audit(
            repo,
            "CHAT_OWNER_MESSAGE",
            task_id=task_id,
            payload={"speaker_code": "OWNER", "speaker_label": "Ты", "text": message},
        )
        replies = _chat_reply_texts(task, message)
        for reply in replies:
            speaker = _chat_speaker(reply["speaker_code"])
            log_audit(
                repo,
                "CHAT_TEAM_REPLY",
                task_id=task_id,
                payload={
                    "speaker_code": speaker["code"],
                    "speaker_label": speaker["label"],
                    "text": reply["text"],
                },
            )
        return {"ok": True, "messages": _list_chat_messages(session, task_id)}


@router.post("/tasks/{task_id}/approve")
async def api_approve_task(task_id: int):
    """Owner approve для задачи."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return apply_owner_decision(repo, task_id, "approve", source="api")


@router.post("/tasks/{task_id}/rework")
async def api_rework_task(task_id: int):
    """Owner rework для задачи."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return apply_owner_decision(repo, task_id, "rework", source="api")


@router.post("/tasks/{task_id}/clarify")
async def api_clarify_task(task_id: int):
    """Owner clarify для задачи."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return apply_owner_decision(repo, task_id, "clarify", source="api")


@router.post("/tasks/{task_id}/merged")
async def api_mark_merged(task_id: int):
    """Подтвердить ручной merge Owner'ом."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return apply_merge_confirmation(repo, task_id, source="api")


@router.get("/tasks/{task_id}/logs")
async def api_get_logs(task_id: int):
    """Логи по задаче (audit_events без секретов)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        events = _query_audit_events(session, task_id=task_id, include_api_requests=True).order_by(AuditEvent.created_at).all()
        logs = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "payload": _safe_payload(event.payload_json),
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]
        return {"logs": logs}
