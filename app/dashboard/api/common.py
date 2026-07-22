# app/dashboard/api/common.py — shared helpers, models, constants for API sub-routers.

import asyncio
import base64
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError

from app.dashboard.documents import (
    build_task_documents,
    latest_verdict_handoff,
    list_regular_handoffs,
    preview_document_bytes,
    read_task_document,
)
from app.orchestrator.triage import run_triage
from app.orchestrator.sync_run import run_sync_orchestration
from app.orchestrator.runtime import OrchestrationCancelled, get_orchestration_runtime
from app.storage.models import AuditEvent, Handoff
from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.sot_compat import execution_event_to_public_dict, run_to_public_dict
from app.shared.auth import require_owner_key
from app.shared.redaction import redact, redact_dict, scrub_secrets
from app.business_execution.learning_hooks import aggregate_all_pack_performance
from app.business_execution.revenue import compute_revenue_metrics_from_tasks
from app.business_execution.growth_engine import build_growth_api_insight, build_growth_insight
from app.business_execution.owner_checklist import (
    classify_owner_day_status,
    compute_data_health,
    owner_daily_checklist_bullets,
)
from app.shared.audit import log_audit, log_decision
from app.shared.system_health import collect_system_health
from app.intake import NormalizeIntakeRequest, normalize_intake
from app.intake.normalize import response_to_public_dict

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts"))
DEFAULT_EVENT_LIMIT = 20
MAX_EVENT_LIMIT = 50
TASK_LIVE_POLL_INTERVAL_MS = 4000
ATTACHMENT_STEP_NAME = "OWNER_ATTACHMENT"
ATTACHMENT_DOCUMENT_ROLE = "source_attachment"
ALLOWED_ATTACHMENT_SUFFIXES = {".md", ".txt", ".docx"}
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
CHAT_EVENT_TYPES = {"CHAT_OWNER_MESSAGE", "CHAT_TEAM_REPLY"}
LIVE_HIDDEN_EVENT_TYPES = {"api_request", *CHAT_EVENT_TYPES}
STARTABLE_TASK_STATUSES = {"NEW", "REWORK", "NEED_INFO"}
APPROVABLE_TASK_STATUSES = {"WAIT_OWNER"}
CLARIFYABLE_TASK_STATUSES = {"WAIT_OWNER"}
REWORKABLE_TASK_STATUSES = {"WAIT_OWNER", "EXECUTION_READY", "APPROVED_WAIT_MERGE", "DONE", "NEED_INFO", "REWORK"}
MERGEABLE_TASK_STATUSES = {"APPROVED_WAIT_MERGE"}
OWNER_DECISION_STEP = "OWNER_DECISION"
OWNER_CLARIFICATION_STEP = "OWNER_CLARIFICATION"
OWNER_REWORK_STEP = "OWNER_REWORK_DECISION"
OWNER_MERGE_STEP = "OWNER_MERGE_CONFIRMATION"
CACHE_TTL_SECONDS = 180
_BUSINESS_CACHE: dict[str, object] = {
    "updated_at_ts": 0.0,
    "metrics_payload": None,
    "growth_payload": None,
    "data_health_payload": None,
}
RUNNER_PHASE_LABELS = {
    "idle": "Ожидание",
    "queued": "В очереди",
    "triage": "Триаж",
    "pipeline": "Pipeline",
    "roundtable": "Совещание",
    "court": "Суд",
    "finalize": "Финализация",
}
CHAT_QUICK_PROMPTS = [
    "Что сейчас делает команда по этой миссии?",
    "Какие риски по задаче самые важные?",
    "Что мне нужно сделать следующим шагом?",
]


def _cache_is_fresh() -> bool:
    updated = float(_BUSINESS_CACHE.get("updated_at_ts") or 0.0)
    return (datetime.utcnow().timestamp() - updated) <= CACHE_TTL_SECONDS


def _build_business_cache_payload(tasks: list[object]) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    active = [t for t in tasks if t.status not in {"DONE", "ARCHIVED"}]
    completed = [t for t in tasks if t.status in {"DONE", "ARCHIVED"}]
    business_effect = [t for t in tasks if (t.business_type or t.impact_level)]

    action_rows = []
    for t in tasks:
        if not isinstance(t.business_action_json, dict):
            continue
        ai = t.business_action_json.get("action_instance")
        if isinstance(ai, dict):
            action_rows.append(ai)
    actions_started = len([a for a in action_rows if a.get("started_at")])
    actions_completed = len([a for a in action_rows if a.get("status") == "done"])
    useful_actions = len([a for a in action_rows if "не сработ" not in str(a.get("owner_feedback") or "").lower() and a.get("status") == "done"])
    useless_actions = len([a for a in action_rows if a.get("status") == "skipped" or "не сработ" in str(a.get("owner_feedback") or "").lower()])

    pack_perf = aggregate_all_pack_performance(tasks)
    revenue_metrics = compute_revenue_metrics_from_tasks(tasks)
    growth = build_growth_insight(tasks)
    pack_learning = {
        k: {
            "generated": v.get("total_generated", 0),
            "success_rate": v.get("success_rate", 0.0),
            "failure_rate": v.get("failure_rate", 0.0),
        }
        for k, v in pack_perf.items()
    }
    metrics_payload = {
        "project_metrics": {
            "active_tasks": len(active),
            "completed_tasks": len(completed),
            "business_effect_tasks": len(business_effect),
        },
        "system_funnel": {
            "tasks_to_artifacts": len([t for t in tasks if getattr(t, "handoffs", None)]),
            "artifacts_to_actions": len([t for t in tasks if t.business_action_json]),
            "actions_to_result": len([t for t in tasks if t.business_action_json and t.status in {"DONE", "ARCHIVED"}]),
        },
        "execution_feedback": {
            "actions_started": actions_started,
            "actions_completed": actions_completed,
            "useful_actions": useful_actions,
            "useless_actions": useless_actions,
        },
        "pack_learning": pack_learning,
        "revenue_metrics": revenue_metrics,
        "growth_insight": growth,
    }
    growth_payload = build_growth_api_insight(tasks)
    data_health_payload = compute_data_health(tasks)
    return metrics_payload, growth_payload, data_health_payload


def _get_cached_business_payload(repo: TaskRepository) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if _cache_is_fresh():
        metrics_cached = _BUSINESS_CACHE.get("metrics_payload")
        growth_cached = _BUSINESS_CACHE.get("growth_payload")
        health_cached = _BUSINESS_CACHE.get("data_health_payload")
        if isinstance(metrics_cached, dict) and isinstance(growth_cached, dict) and isinstance(health_cached, dict):
            return metrics_cached, growth_cached, health_cached

    tasks = repo.get_all_tasks()
    metrics_payload, growth_payload, data_health_payload = _build_business_cache_payload(tasks)
    _BUSINESS_CACHE["metrics_payload"] = metrics_payload
    _BUSINESS_CACHE["growth_payload"] = growth_payload
    _BUSINESS_CACHE["data_health_payload"] = data_health_payload
    _BUSINESS_CACHE["updated_at_ts"] = datetime.utcnow().timestamp()
    return metrics_payload, growth_payload, data_health_payload


def _signed_dashboard_task_path(task_id: int) -> str:
    """Относительный путь HTML-задачи с ?link= для браузера без X-API-Key."""
    from urllib.parse import quote

    from app.shared.dashboard_link import sign_task_link

    tok = sign_task_link(task_id)
    if not tok:
        return f"/tasks/{task_id}"
    return f"/tasks/{task_id}?link={quote(tok, safe='')}"


def _unified_mission_bundle(task_id: int) -> dict:
    """
    Продуктовый алиас mission ↔ task: один source of truth в store задач,
    два входа (Telegram / Dashboard) смотрят на одну и ту же запись и события.
    """
    tid = int(task_id)
    return {
        "mission_id": tid,
        "task_id": tid,
        "canonical_store": "tasks",
        "entrypoints": {
            "dashboard_task": _signed_dashboard_task_path(tid),
            "dashboard_office": f"/office/tasks/{tid}",
            "api_scene": f"/api/tasks/{tid}/scene",
            "api_mission_scene": f"/api/missions/{tid}/scene",
            "api_events": f"/api/events?mission_id={tid}",
            "api_thread": f"/api/missions/{tid}/thread",
            "api_thread_alt": f"/api/tasks/{tid}/thread",
        },
        "shared_across_channels": {
            "handoffs": True,
            "audit_timeline": True,
            "documents_attachments": True,
            "summary_verdict": True,
        },
    }


STEP_PERSONAS = {
    "COORDINATOR": {"label": "Координатор", "zone": "reception", "animation": "accept"},
    "PS": {"label": "Продуктовый стратег", "zone": "strategy", "animation": "think"},
    "PM": {"label": "Менеджер поставки", "zone": "management", "animation": "brief"},
    "UX": {"label": "UX-дизайнер", "zone": "design", "animation": "sketch"},
    "FE": {"label": "Frontend инженер", "zone": "frontend", "animation": "build"},
    "BE": {"label": "Backend инженер", "zone": "backend", "animation": "build"},
    "FE_BE": {"label": "Fullstack инженер", "zone": "delivery", "animation": "build"},
    "ARCH": {"label": "Архитектор", "zone": "architecture", "animation": "review"},
    "QA": {"label": "QA ревьюер", "zone": "qa", "animation": "review"},
    "DEVOPS": {"label": "DevOps инженер", "zone": "ops", "animation": "ops"},
    "CONTENT": {"label": "Контент-редактор", "zone": "content", "animation": "write"},
    "BRAND": {"label": "Бренд-ревьюер", "zone": "meeting", "animation": "review"},
    "RC": {"label": "Reality checker", "zone": "meeting", "animation": "debate"},
    "RC2": {"label": "Независимый ревьюер", "zone": "meeting", "animation": "debate"},
    "LEGAL": {"label": "Юрист", "zone": "meeting", "animation": "review"},
    "FIN": {"label": "Финансовый аналитик", "zone": "meeting", "animation": "review"},
    "DATA": {"label": "Дата-аналитик", "zone": "analytics", "animation": "analyze"},
    "EVENT": {"label": "Event-оператор", "zone": "operations", "animation": "plan"},
    "ML_PROMPT": {"label": "Prompt инженер", "zone": "lab", "animation": "think"},
    "SEC": {"label": "Security ревьюер", "zone": "meeting", "animation": "review"},
    "JUDGE": {"label": "Судья", "zone": "court", "animation": "decide"},
    "OWNER": {"label": "Владелец", "zone": "owner", "animation": "approve"},
}

STATUS_SCENES = {
    "NEW": {"title": "Приёмная", "subtitle": "Новая миссия поступила в штаб.", "zone": "reception", "animation": "arrive"},
    "TRIAGED": {"title": "Разбор миссии", "subtitle": "Координатор определил домен, критичность и режим работы.", "zone": "strategy", "animation": "classify"},
    "IN_PIPELINE": {"title": "Рабочий коридор", "subtitle": "Агенты по очереди готовят handoff и передают дело дальше.", "zone": "worklane", "animation": "handoff"},
    "IN_ROUNDTABLE": {"title": "Переговорная", "subtitle": "Команда обсуждает риски, компромиссы и подтверждает план.", "zone": "meeting", "animation": "debate"},
    "IN_COURT": {"title": "Суд решений", "subtitle": "Формируется итоговая позиция и финальный отчёт.", "zone": "court", "animation": "judge"},
    "WAIT_OWNER": {"title": "Стол владельца", "subtitle": "Система ждёт управленческого решения по готовому результату.", "zone": "owner", "animation": "wait-owner"},
    "EXECUTION_READY": {
        "title": "Запуск в Cursor",
        "subtitle": "Подготовлены промпты и план — выполните работу в репозитории, затем при необходимости снова запустите pipeline.",
        "zone": "owner",
        "animation": "wait-owner",
    },
    "APPROVED_WAIT_MERGE": {"title": "PR готов", "subtitle": "Одобрено. Остался ручной merge и подтверждение закрытия задачи.", "zone": "owner", "animation": "merge"},
    "NEED_INFO": {"title": "Нужно уточнение", "subtitle": "Владелец запросил дополнительные вводные.", "zone": "owner", "animation": "clarify"},
    "REWORK": {"title": "Доработка", "subtitle": "Миссия отправлена на повторный круг с новыми замечаниями.", "zone": "worklane", "animation": "rework"},
    "DONE": {"title": "Архив миссий", "subtitle": "Задача успешно завершена и передана в архив штаба.", "zone": "archive", "animation": "done"},
    "ARCHIVED": {"title": "Архив", "subtitle": "Миссия хранится в архиве и доступна для просмотра.", "zone": "archive", "animation": "archive"},
}

EVENT_LABELS = {
    "task_created": "Задача создана",
    "task_file_uploaded": "Файл добавлен",
    "triage_done": "Триаж завершён",
    "pipeline_start": "Pipeline запущен",
    "pipeline_done": "Pipeline завершён",
    "roundtable_done": "Совещание завершено",
    "orchestration_done": "Оркестрация завершена",
    "orchestration_error": "Ошибка оркестрации",
    "pipeline_background_started": "AI-Team запущен в фоне",
    "pipeline_background_completed": "Фоновый проход завершён",
    "pipeline_background_stopped": "AI-Team остановлен",
    "pipeline_background_failed": "Фоновый проход завершился с ошибкой",
    "CHAT_OWNER_MESSAGE": "Сообщение владельца",
    "CHAT_TEAM_REPLY": "Ответ команды",
    "OWNER_APPROVED": "Владелец утвердил",
    "OWNER_REWORK": "Владелец отправил на доработку",
    "OWNER_CLARIFY": "Владелец запросил уточнение",
    "OWNER_MERGED": "Слияние подтверждено",
}

EVENT_SEVERITIES = {
    "task_created": "info",
    "task_file_uploaded": "info",
    "triage_done": "success",
    "pipeline_start": "info",
    "pipeline_done": "success",
    "roundtable_done": "success",
    "orchestration_done": "success",
    "orchestration_error": "error",
    "pipeline_background_started": "info",
    "pipeline_background_completed": "success",
    "pipeline_background_stopped": "warn",
    "pipeline_background_failed": "error",
    "CHAT_OWNER_MESSAGE": "info",
    "CHAT_TEAM_REPLY": "info",
    "OWNER_APPROVED": "success",
    "OWNER_REWORK": "warn",
    "OWNER_CLARIFY": "warn",
    "OWNER_MERGED": "success",
}

EVENT_STATUS_AFTER = {
    "task_created": "NEW",
    "task_file_uploaded": None,
    "triage_done": "TRIAGED",
    "pipeline_start": "IN_PIPELINE",
    "pipeline_done": "IN_PIPELINE",
    "roundtable_done": "IN_ROUNDTABLE",
    "pipeline_background_stopped": "REWORK",
    "OWNER_CLARIFY": "NEED_INFO",
    "OWNER_REWORK": "REWORK",
    "OWNER_MERGED": "DONE",
}


def run_task_orchestration(repo: TaskRepository, task_id: int, source: str = "api", control=None) -> dict:
    """Синхронный прогон triage -> pipeline -> roundtable -> court (делегирует в app.orchestrator.sync_run)."""
    result = run_sync_orchestration(repo, task_id, source=source, control=control)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


def _merge_status_summary(prefix: str, existing_summary: str | None = None) -> str:
    existing = (existing_summary or "").strip()
    if existing and existing not in prefix:
        return f"{prefix} Командный итог: {existing}"[:1200]
    return prefix[:1200]


def _owner_status_summary(task, new_status: str, decision: str) -> str:
    if decision == "approve":
        if new_status == "APPROVED_WAIT_MERGE":
            return _merge_status_summary(
                "Owner утвердил результат. AI-Team закончил работу. Осталось выполнить ручной merge и подтвердить закрытие задачи.",
                task.summary,
            )
        return _merge_status_summary(
            "Owner утвердил результат. Миссия завершена, активный цикл AI-Team остановлен, финальные документы доступны в архиве.",
            task.summary,
        )
    if decision == "clarify":
        return _merge_status_summary(
            "Owner запросил уточнение. Текущий цикл остановлен до новых вводных и следующего ручного запуска AI-Team.",
            task.summary,
        )
    if decision == "merged":
        return _merge_status_summary(
            "Merge подтверждён. Миссия окончательно завершена, активных процессов больше нет, итоговые документы сохранены в архиве.",
            task.summary,
        )
    return (task.summary or "")[:1200]


def _max_handoff_step_index(task) -> int:
    return max((handoff.step_index for handoff in getattr(task, "handoffs", []) or []), default=-1)


def _task_upload_dir(task_id: int) -> Path:
    return ARTIFACTS_DIR / "tasks" / f"task_{task_id}" / "uploads"


def _safe_upload_name(name: str) -> str:
    candidate = Path(str(name or "")).name.strip()
    if not candidate:
        return ""
    return re.sub(r"[^\w.\- ]+", "_", candidate, flags=re.UNICODE)


def _unique_upload_path(directory: Path, file_name: str) -> Path:
    candidate = directory / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        attempt = directory / f"{stem}_{index}{suffix}"
        if not attempt.exists():
            return attempt
        index += 1


def _decode_attachment_body(file_body: dict) -> tuple[str, bytes]:
    if not isinstance(file_body, dict):
        raise HTTPException(status_code=400, detail="Each file must be an object")
    file_name = _safe_upload_name(file_body.get("name", ""))
    if not file_name:
        raise HTTPException(status_code=400, detail="File name is required")
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
        raise HTTPException(status_code=400, detail="Поддерживаются только .md, .txt и .docx")
    try:
        raw_bytes = base64.b64decode(file_body.get("content_base64", ""), validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Некорректное содержимое файла {file_name}") from exc
    if len(raw_bytes) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail=f"Файл {file_name} превышает лимит 5 МБ")
    return file_name, raw_bytes


def _attachment_summary_lines(file_name: str, preview_excerpt: str) -> list[str]:
    summary = [f"Владелец добавил файл {file_name} в контекст миссии."]
    if preview_excerpt:
        summary.append(f"Короткое содержание: {preview_excerpt}")
    else:
        summary.append("Файл сохранён в проекте и доступен команде как входной документ.")
    return summary


def _replace_owner_document(repo: TaskRepository, task, *, step_name: str, filename: str, title: str, subtitle: str, summary_lines: list[str], body_lines: list[str], document_role: str):
    owner_dir = ARTIFACTS_DIR / "tasks" / f"task_{task.id}" / "owner"
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / filename
    path.write_text("\n".join(body_lines).strip() + "\n", encoding="utf-8")

    existing_rows = (
        repo.session.query(Handoff)
        .filter(Handoff.task_id == task.id, Handoff.step_name == step_name)
        .all()
    )
    for row in existing_rows:
        repo.session.delete(row)
    repo.session.commit()

    repo.add_handoff(
        task.id,
        _max_handoff_step_index(repo.get_task(task.id)) + 1,
        step_name,
        {
            "document_role": document_role,
            "document_title": title,
            "document_subtitle": subtitle,
            "summary": summary_lines,
            "next_action": summary_lines[0] if summary_lines else "",
        },
        str(path),
    )
    return str(path)


def _write_owner_approve_document(repo: TaskRepository, task, new_status: str) -> str:
    next_step = (
        "Сделать ручной merge и затем подтвердить его в сцене задачи."
        if new_status == "APPROVED_WAIT_MERGE"
        else "Открыть итоговые документы и при необходимости закрыть рабочий цикл."
    )
    body = [
        "# Решение владельца",
        "",
        "## Что произошло",
        "Владелец утвердил результат работы AI-Team.",
        "",
        "## Текущий статус",
        f"- Статус задачи: {new_status}",
        f"- PR привязан: {'Да' if task.pr_url else 'Нет'}",
        "",
        "## Что это значит",
        "Командный verdict принят как рабочее основание для следующего шага.",
        "Новый цикл AI-Team сейчас не требуется.",
        "",
        "## Что делать дальше",
        f"- {next_step}",
        "- Использовать финальный отчёт и вердикт как основные документы по миссии.",
    ]
    summary_lines = [
        "Владелец утвердил результат. Документ фиксирует, что именно принято и какой следующий шаг теперь ожидается.",
        next_step,
    ]
    return _replace_owner_document(
        repo,
        task,
        step_name=OWNER_DECISION_STEP,
        filename="owner_decision.md",
        title="Решение владельца",
        subtitle="Фиксация управленческого подтверждения",
        summary_lines=summary_lines,
        body_lines=body,
        document_role="owner_decision",
    )


def _write_owner_clarification_document(repo: TaskRepository, task) -> str:
    body = [
        "# Запрос владельца на уточнение",
        "",
        "## Что произошло",
        "Владелец запросил дополнительный контекст перед следующим запуском AI-Team.",
        "",
        "## Что это значит",
        "Текущий цикл остановлен на паузу ожидания новых вводных.",
        "",
        "## Что делать дальше",
        "- Добавить недостающие данные, ограничения или уточнения по задаче.",
        "- После обновления контекста снова запустить AI-Team вручную.",
    ]
    summary_lines = [
        "Владелец запросил уточнение. До новых вводных следующий цикл AI-Team не должен стартовать.",
        "После обновления контекста запусти AI-Team заново.",
    ]
    return _replace_owner_document(
        repo,
        task,
        step_name=OWNER_CLARIFICATION_STEP,
        filename="owner_clarification.md",
        title="Запрос владельца на уточнение",
        subtitle="Пауза перед следующим запуском",
        summary_lines=summary_lines,
        body_lines=body,
        document_role="owner_clarification",
    )


def _write_owner_rework_document(repo: TaskRepository, task) -> str:
    body = [
        "# Решение владельца о доработке",
        "",
        "## Что произошло",
        "Владелец вернул миссию на доработку и инициировал новый цикл работы команды.",
        "",
        "## Что это значит",
        "Предыдущий результат больше не считается окончательным.",
        "Команда должна пройти цикл AI-Team заново с учётом замечаний владельца.",
        "",
        "## Что делать дальше",
        "- Дождаться нового прохода AI-Team.",
        "- После завершения сравнить новый итог с предыдущим verdict и отчётом.",
    ]
    summary_lines = [
        "Владелец отправил задачу на доработку. Прежний результат больше не считается окончательным.",
        "Команда проходит новый цикл AI-Team.",
    ]
    return _replace_owner_document(
        repo,
        task,
        step_name=OWNER_REWORK_STEP,
        filename="owner_rework.md",
        title="Решение владельца о доработке",
        subtitle="Новый цикл работы команды",
        summary_lines=summary_lines,
        body_lines=body,
        document_role="owner_rework",
    )


def _write_owner_merge_document(repo: TaskRepository, task) -> str:
    body = [
        "# Подтверждение merge",
        "",
        "## Что произошло",
        "Владелец подтвердил, что ручной merge выполнен.",
        "",
        "## Что это значит",
        "Миссия окончательно завершена. Активных owner-решений и фоновых процессов больше нет.",
        "",
        "## Что делать дальше",
        "- Использовать финальные документы как архивный итог по задаче.",
        "- Если понадобится новый цикл, вернуть задачу на доработку из нового контекста.",
    ]
    summary_lines = [
        "Merge подтверждён владельцем. Это финальная фиксация закрытия миссии.",
        "Дальше доступны только архив и итоговые документы.",
    ]
    return _replace_owner_document(
        repo,
        task,
        step_name=OWNER_MERGE_STEP,
        filename="merge_confirmation.md",
        title="Подтверждение merge",
        subtitle="Финальная фиксация закрытия миссии",
        summary_lines=summary_lines,
        body_lines=body,
        document_role="owner_merge_confirmation",
    )


def _task_can_start_background(task) -> bool:
    return task.status in STARTABLE_TASK_STATUSES


def _task_can_chat(task) -> bool:
    return task.status not in {"ARCHIVED"}


def _start_action_reason(task, runner: dict) -> str:
    if runner.get("is_active"):
        return "AI-Team уже работает по этой миссии."
    if task.status in STARTABLE_TASK_STATUSES:
        return "Можно запускать новый проход AI-Team."
    if task.status == "WAIT_OWNER":
        return "Сейчас ждём решение владельца, а не новый запуск."
    if task.status == "APPROVED_WAIT_MERGE":
        return "Сначала нужен ручной merge, а не новый запуск."
    if task.status in {"DONE", "ARCHIVED"}:
        return "Для нового цикла сначала верни задачу на доработку."
    return "Запуск сейчас недоступен для этой фазы."


def _stop_action_reason(task, runner: dict) -> str:
    if runner.get("is_active"):
        return "Можно безопасно остановить текущий фоновый проход."
    return "Сейчас нет активного фонового прохода AI-Team."


def _build_owner_actions(task, runner: dict) -> dict:
    busy_reason = "Пока AI-Team выполняет задачу, owner-решения недоступны. Сначала останови проход или дождись завершения."
    can_approve = task.status in APPROVABLE_TASK_STATUSES and not runner.get("is_active")
    can_clarify = task.status in CLARIFYABLE_TASK_STATUSES and not runner.get("is_active")
    can_rework = task.status in REWORKABLE_TASK_STATUSES and not runner.get("is_active")
    can_mark_merged = task.status in MERGEABLE_TASK_STATUSES and bool(task.pr_url) and not runner.get("is_active")

    if runner.get("is_active"):
        approve_reason = clarify_reason = rework_reason = merged_reason = busy_reason
    else:
        approve_reason = "Можно зафиксировать owner approve и перевести задачу дальше." if can_approve else (
            "Approve доступен только когда команда уже завершила работу и ждёт owner."
        )
        clarify_reason = "Можно остановить цикл до получения дополнительных вводных." if can_clarify else (
            "Уточнение запрашивается только в фазе ожидания owner."
        )
        rework_reason = "Можно открыть новый цикл доработки для команды." if can_rework else (
            "На этой фазе доработка не нужна: либо сначала запусти AI-Team, либо дождись owner/merge шага."
        )
        merged_reason = "Можно подтверждать merge после фактического ручного слияния." if can_mark_merged else (
            "Подтверждение merge доступно только после approve и при наличии PR."
        )

    summary = {
        "NEW": "Сейчас задача ещё не запускалась. Доступно только управление запуском.",
        "WAIT_OWNER": "Команда завершила работу. Сейчас владелец должен принять решение.",
        "APPROVED_WAIT_MERGE": "Owner уже утвердил результат. Остался только ручной merge и его подтверждение.",
        "NEED_INFO": "Цикл остановлен до уточнения контекста. После новых вводных можно запустить AI-Team снова.",
        "REWORK": "Задача открыта на новый цикл доработки. Её можно запускать повторно.",
        "DONE": "Миссия завершена. Можно читать документы или открыть новый цикл доработки.",
        "ARCHIVED": "Миссия в архиве. Операционные действия больше не нужны.",
    }.get(task.status, "Ориентируйся на текущую фазу и доступные owner-actions.")

    return {
        "can_decide": can_approve or can_clarify,
        "can_approve": can_approve,
        "can_rework": can_rework,
        "can_clarify": can_clarify,
        "can_mark_merged": can_mark_merged,
        "approve_reason": approve_reason,
        "rework_reason": rework_reason,
        "clarify_reason": clarify_reason,
        "merged_reason": merged_reason,
        "summary": summary,
    }


def _build_control_state(task, runner: dict, owner_actions: dict) -> dict:
    if runner.get("is_active"):
        status_summary = f"AI-Team реально работает в фоне. Текущая фаза: {runner.get('phase_label', 'в работе')}."
        owner_waiting_for = "Сейчас owner-решения заблокированы до безопасной остановки или завершения прохода."
    elif task.status == "WAIT_OWNER":
        status_summary = "AI-Team уже закончил. Сейчас система ничего не исполняет и ждёт только owner-решение."
        owner_waiting_for = "Открой verdict, затем выбери approve, rework или clarify."
    elif task.status == "APPROVED_WAIT_MERGE":
        status_summary = "AI-Team уже закончил. Owner approve зафиксирован, но задача ещё не закрыта из-за ожидания merge."
        owner_waiting_for = "Сделай ручной merge и затем подтверди его в сцене."
    elif task.status == "REWORK":
        status_summary = "Задача находится в режиме доработки. Новый цикл ещё не завершён."
        owner_waiting_for = "После исправлений снова запусти AI-Team."
    elif task.status == "NEED_INFO":
        status_summary = "Текущий цикл поставлен на паузу из-за нехватки вводных."
        owner_waiting_for = "Добавь уточнение и затем снова запусти AI-Team."
    elif task.status in {"DONE", "ARCHIVED"}:
        status_summary = "Активных процессов больше нет. Остались только итоговые документы и история."
        owner_waiting_for = "Если нужен новый цикл, используй действие «На доработку»."
    else:
        status_summary = "Смотри фазу миссии и нижнюю панель действий: именно она показывает, что доступно реально сейчас."
        owner_waiting_for = owner_actions.get("summary", "")

    return {
        "status_summary": status_summary,
        "owner_waiting_for": owner_waiting_for,
        "start_reason": _start_action_reason(task, runner),
        "stop_reason": _stop_action_reason(task, runner),
    }


def apply_owner_decision(repo: TaskRepository, task_id: int, decision: str, source: str = "api") -> dict:
    """Применить owner decision с теми же статусами, что и в Telegram."""
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    runner = _runner_snapshot(task_id)
    owner_actions = _build_owner_actions(task, runner)
    normalized = (decision or "").strip().lower()
    if normalized not in {"approve", "rework", "clarify"}:
        raise HTTPException(status_code=400, detail="decision must be approve, rework or clarify")

    if normalized == "approve":
        if not owner_actions["can_approve"]:
            raise HTTPException(status_code=409, detail=owner_actions["approve_reason"])
        log_decision(repo, task_id, decision="a", owner_approval=True)
        new_status = "APPROVED_WAIT_MERGE" if task.pr_url else "DONE"
        updated = repo.update_task(task_id, status=new_status, summary=_owner_status_summary(task, new_status, "approve"))
        fresh_task = repo.get_task(task_id)
        _write_owner_approve_document(repo, fresh_task, new_status)
        log_audit(
            repo,
            "OWNER_APPROVED",
            task_id=task_id,
            payload={"decision": "approve", "source": source, "status_after": new_status},
        )
        return {"id": task_id, "status": updated.status if updated else new_status, "decision": normalized}

    if normalized == "clarify":
        if not owner_actions["can_clarify"]:
            raise HTTPException(status_code=409, detail=owner_actions["clarify_reason"])
        log_decision(repo, task_id, decision="c", owner_approval=False)
        updated = repo.update_task(task_id, status="NEED_INFO", summary=_owner_status_summary(task, "NEED_INFO", "clarify"))
        fresh_task = repo.get_task(task_id)
        _write_owner_clarification_document(repo, fresh_task)
        log_audit(
            repo,
            "OWNER_CLARIFY",
            task_id=task_id,
            payload={"decision": "clarify", "source": source, "status_after": "NEED_INFO"},
        )
        return {"id": task_id, "status": updated.status if updated else "NEED_INFO", "decision": normalized}

    if not owner_actions["can_rework"]:
        raise HTTPException(status_code=409, detail=owner_actions["rework_reason"])
    log_decision(repo, task_id, decision="r", owner_approval=False)
    repo.update_task(task_id, status="REWORK")
    fresh_task = repo.get_task(task_id)
    _write_owner_rework_document(repo, fresh_task)
    log_audit(
        repo,
        "OWNER_REWORK",
        task_id=task_id,
        payload={"decision": "rework", "source": source, "status_after": "REWORK"},
    )
    result = run_task_orchestration(repo, task_id, source=f"{source}_rework")
    return {"id": task_id, "decision": normalized, **result}


def apply_merge_confirmation(repo: TaskRepository, task_id: int, source: str = "api") -> dict:
    """Подтвердить ручной merge и закрыть задачу."""
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    runner = _runner_snapshot(task_id)
    owner_actions = _build_owner_actions(task, runner)
    if not owner_actions["can_mark_merged"]:
        raise HTTPException(status_code=409, detail=owner_actions["merged_reason"])

    log_decision(repo, task_id, decision="merged", owner_approval=True)
    updated = repo.update_task(task_id, status="DONE", summary=_owner_status_summary(task, "DONE", "merged"))
    fresh_task = repo.get_task(task_id)
    _write_owner_merge_document(repo, fresh_task)
    log_audit(
        repo,
        "OWNER_MERGED",
        task_id=task_id,
        payload={"decision": "i_merged", "source": source, "status_after": "DONE"},
    )
    return {"id": task_id, "status": updated.status if updated else "DONE", "decision": "merged"}


def _runner_phase_label(phase: str) -> str:
    return RUNNER_PHASE_LABELS.get(phase or "idle", phase or "idle")


def _runner_snapshot(task_id: int) -> dict:
    runtime = get_orchestration_runtime()
    snapshot = runtime.snapshot(task_id)
    snapshot["phase_label"] = _runner_phase_label(snapshot.get("phase", "idle"))
    return snapshot


def _log_background_stop(repo: TaskRepository, task_id: int, control) -> dict:
    current = repo.get_task(task_id)
    if not current:
        raise OrchestrationCancelled("Task not found while stopping background orchestration.")
    new_status = current.status if current.status in {"DONE", "ARCHIVED"} else "REWORK"
    phase_label = control.snapshot().get("phase_label") or "текущая фаза"
    summary = (
        f"AI-Team остановлен пользователем на фазе {phase_label}. "
        "Частично собранный контекст сохранён. Для продолжения снова запустите AI-Team."
    )[:1200]
    updated = repo.update_task(task_id, status=new_status, summary=summary)
    log_audit(
        repo,
        "pipeline_background_stopped",
        task_id=task_id,
        payload={
            "phase": control.snapshot().get("phase"),
            "phase_label": phase_label,
            "source": "background",
            "status_after": updated.status if updated else new_status,
        },
    )
    raise OrchestrationCancelled(summary)


def _background_orchestration_target(task_id: int, source: str):
    def _runner(control):
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            try:
                control.set_phase("triage", message="Координатор разбирает новую миссию.", current_step="COORDINATOR")
                result = run_task_orchestration(repo, task_id, source=source, control=control)
                log_audit(
                    repo,
                    "pipeline_background_completed",
                    task_id=task_id,
                    payload={"source": source, "status_after": result.get("status")},
                )
                return result
            except OrchestrationCancelled:
                _log_background_stop(repo, task_id, control)
            except Exception as exc:
                current = repo.get_task(task_id)
                status_after = current.status if current else "REWORK"
                if current and current.status not in {"DONE", "ARCHIVED"}:
                    status_after = "REWORK"
                    repo.update_task(
                        task_id,
                        status=status_after,
                        summary=f"AI-Team остановился из-за ошибки. Проверь журнал и при необходимости перезапусти миссию. Ошибка: {str(exc)[:260]}",
                    )
                log_audit(
                    repo,
                    "pipeline_background_failed",
                    task_id=task_id,
                    payload={"error": str(exc), "source": source, "status_after": status_after},
                )
                raise

    return _runner


def _start_background_orchestration(task_id: int, source: str) -> dict:
    runtime = get_orchestration_runtime()
    return runtime.start(task_id, source=source, target=_background_orchestration_target(task_id, source))


def _chat_speaker(code: str) -> dict:
    if code == "OWNER":
        return {"code": "OWNER", "label": "Ты", "zone": "owner"}
    persona = _persona_for_step(code)
    return {"code": persona["code"], "label": persona["label"], "zone": persona["zone"]}


def _step_from_task_status(task) -> str:
    return {
        "NEW": "COORDINATOR",
        "TRIAGED": "PS",
        "IN_PIPELINE": "PM",
        "IN_ROUNDTABLE": "RC",
        "IN_COURT": "JUDGE",
        "EXECUTION_READY": "OWNER",
        "WAIT_OWNER": "OWNER",
        "APPROVED_WAIT_MERGE": "OWNER",
        "NEED_INFO": "OWNER",
        "REWORK": "PM",
        "DONE": "OWNER",
        "ARCHIVED": "OWNER",
    }.get(task.status, "COORDINATOR")


def _chat_current_persona(task) -> dict:
    handoffs = list_regular_handoffs(task)
    if handoffs:
        return _persona_for_step(handoffs[-1].step_name)
    return _persona_for_step(_step_from_task_status(task))


def _chat_next_persona(task) -> dict:
    current = _chat_current_persona(task)
    if task.status in {"WAIT_OWNER", "EXECUTION_READY", "APPROVED_WAIT_MERGE", "DONE", "ARCHIVED"}:
        return _persona_for_step("OWNER")
    if current["code"] in {"COORDINATOR", "PS"}:
        return _persona_for_step("PM")
    if current["code"] in {"PM", "QA", "DEVOPS", "FE", "BE", "ARCH"}:
        return _persona_for_step("RC")
    if current["code"] in {"RC", "SEC", "LEGAL", "FIN"}:
        return _persona_for_step("JUDGE")
    return _persona_for_step("OWNER")


def _chat_top_risks(task) -> list[str]:
    return [risk.get("issue", "") for risk in (task.risk_table_json or []) if risk.get("issue")][:2]


def _chat_reply_texts(task, message: str) -> list[dict]:
    text = (message or "").strip()
    if not text:
        return []

    lowered = text.lower()
    current = _chat_current_persona(task)
    nxt = _chat_next_persona(task)
    risk_items = _chat_top_risks(task)
    base_summary = (task.summary or "").strip()
    current_label = STEP_PERSONAS.get(current["code"], {}).get("label", current["label"])
    next_label = STEP_PERSONAS.get(nxt["code"], {}).get("label", nxt["label"])
    scene_title = STATUS_SCENES.get(task.status, {}).get("title", task.status)
    runner = _runner_snapshot(task.id)
    owner_actions = _build_owner_actions(task, runner)
    control_state = _build_control_state(task, runner, owner_actions)

    if any(token in lowered for token in ["что сейчас", "что происходит", "статус", "где задача"]):
        return [
            {
                "speaker_code": current["code"],
                "text": f"Сейчас миссия находится в фазе «{scene_title}». {control_state['status_summary']}",
            },
            {
                "speaker_code": nxt["code"],
                "text": f"Следующий практический шаг: {control_state['owner_waiting_for'] or f'{next_label.lower()} подключается после текущей фазы.'}",
            },
        ]

    if any(token in lowered for token in ["риск", "риски", "опасно", "проблем"]):
        lead = "SEC" if risk_items else current["code"]
        first_line = "Главные риски сейчас: " + "; ".join(risk_items) if risk_items else "Явных блокирующих рисков сейчас не зафиксировано."
        second_line = "Если хочешь, разложу риски по приоритету и скажу, что блокирует следующий шаг."
        return [
            {"speaker_code": lead, "text": first_line},
            {"speaker_code": "RC", "text": second_line},
        ]

    if any(token in lowered for token in ["что дальше", "следующий шаг", "дальше", "что делать"]):
        return [
            {
                "speaker_code": current["code"],
                "text": f"По моей части контекст уже собран. Текущая фаза: {scene_title}.",
            },
            {
                "speaker_code": nxt["code"],
                "text": f"Дальше нужен такой шаг: {control_state['owner_waiting_for'] or base_summary or 'ориентируйся на верхний блок состояния и решение владельца.'}",
            },
        ]

    if any(token in lowered for token in ["док", "файл", "verdict", "отчёт", "отчет"]):
        return [
            {
                "speaker_code": "JUDGE",
                "text": "Финальный verdict и отчёт лежат в блоке «Папки отделов». Их можно открыть отдельно или скачать.",
            },
            {
                "speaker_code": current["code"],
                "text": "Если нужно, могу подсказать, какой документ сейчас главный для следующего действия по задаче.",
            },
        ]

    if any(token in lowered for token in ["стоп", "останов", "пауза", "прекрати"]):
        return [
            {
                "speaker_code": "PM",
                "text": "Чтобы реально прервать текущий проход, нажми «Остановить AI-Team». Мы сохраним уже собранный контекст.",
            },
            {
                "speaker_code": "OWNER",
                "text": "После остановки задача перейдёт в состояние, из которого её можно будет снова запустить вручную.",
            },
        ]

    return [
        {
            "speaker_code": current["code"],
            "text": f"По этой миссии вижу следующее: {base_summary or f'сейчас работаем в фазе «{scene_title}» и держим контекст задачи.'}",
        },
        {
            "speaker_code": nxt["code"],
            "text": f"Если нужна конкретика, спроси меня про статус, риски, документы или следующий шаг. Отвечу по делу на русском.",
        },
    ]


def _list_chat_messages(session, task_id: int, limit: int = 30) -> list[dict]:
    rows = (
        session.query(AuditEvent)
        .filter(AuditEvent.task_id == task_id, AuditEvent.event_type.in_(tuple(CHAT_EVENT_TYPES)))
        .order_by(AuditEvent.id.desc())
        .limit(limit)
        .all()
    )
    messages = []
    for row in reversed(rows):
        payload = _safe_payload(row.payload_json)
        speaker_code = payload.get("speaker_code", "OWNER" if row.event_type == "CHAT_OWNER_MESSAGE" else "COORDINATOR")
        speaker = _chat_speaker(speaker_code)
        messages.append(
            {
                "id": row.id,
                "role": "owner" if row.event_type == "CHAT_OWNER_MESSAGE" else "team",
                "speaker_code": speaker["code"],
                "speaker_name": speaker["label"],
                "speaker_zone": speaker["zone"],
                "text": _safe_text(payload.get("text", "")),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return messages


def _safe_text(value) -> str:
    if value is None:
        return ""
    return redact(scrub_secrets(str(value)))


def _safe_payload(payload: dict | None) -> dict:
    return redact_dict(payload or {})


def _event_label(event_type: str) -> str:
    return EVENT_LABELS.get(event_type, (event_type or "event").replace("_", " ").strip() or "event")


def _event_severity(event_type: str, payload: dict) -> str:
    if event_type == "orchestration_done" and payload.get("final_status") == "WAIT_OWNER":
        return "warn"
    return EVENT_SEVERITIES.get(event_type, "info")


def _event_status_after(event_type: str, payload: dict):
    if payload.get("status_after"):
        return payload.get("status_after")
    if event_type == "orchestration_done":
        return payload.get("final_status")
    return EVENT_STATUS_AFTER.get(event_type)


def _event_note(event_type: str, payload: dict) -> str:
    payload = _safe_payload(payload)

    if event_type == "task_created":
        return "Миссия зарегистрирована в системе."
    if event_type == "task_file_uploaded":
        file_name = _safe_text(payload.get("file_name", "документ"))
        count = payload.get("file_count")
        if count and count > 1:
            return f"В миссию добавлен файл {file_name}. Всего в партии: {count}."
        return f"В миссию добавлен файл {file_name}."
    if event_type == "triage_done":
        parts = []
        if payload.get("domain"):
            parts.append(f"Домен: {payload['domain']}")
        if payload.get("task_type"):
            parts.append(f"тип: {payload['task_type']}")
        if payload.get("plan_or_execute"):
            parts.append(f"режим: {payload['plan_or_execute']}")
        return ", ".join(parts) if parts else "Триаж завершён."
    if event_type == "pipeline_start":
        return "Pipeline запущен."
    if event_type == "pipeline_done":
        return f"Handoffs подготовлено: {payload.get('steps', 0)}."
    if event_type == "roundtable_done":
        return f"Рисков зафиксировано: {payload.get('risks', 0)}."
    if event_type == "orchestration_done":
        return f"Итоговый статус: {payload.get('final_status', '-')}."
    if event_type == "orchestration_error":
        return _safe_text(payload.get("error", "Неизвестная ошибка")) or "Неизвестная ошибка"
    if event_type == "pipeline_background_started":
        return "AI-Team переведён в фоновый режим выполнения."
    if event_type == "pipeline_background_completed":
        return "Фоновый проход AI-Team завершён."
    if event_type == "pipeline_background_stopped":
        return f"Остановлено на фазе {payload.get('phase_label', payload.get('phase', '-'))}."
    if event_type == "pipeline_background_failed":
        return _safe_text(payload.get("error", "Фоновый job завершился с ошибкой")) or "Фоновый job завершился с ошибкой"
    if event_type == "CHAT_OWNER_MESSAGE":
        return _safe_text(payload.get("text", "Новое сообщение владельца"))
    if event_type == "CHAT_TEAM_REPLY":
        speaker = payload.get("speaker_label", payload.get("speaker_code", "Команда"))
        return f"{_safe_text(speaker)}: {_safe_text(payload.get('text', 'Ответ команды'))}"
    if event_type.startswith("OWNER_"):
        status_after = payload.get("status_after")
        decision_note = f"Решение owner: {payload.get('decision', '-')}"
        if status_after:
            decision_note = f"{decision_note}. Новый статус: {status_after}."
        return decision_note

    items = []
    for key, value in payload.items():
        if value is None or key in {"request_id", "source", "status_after"}:
            continue
        items.append(f"{key}={value}")
    if not items:
        return "Событие зафиксировано."
    return _safe_text(", ".join(items))[:220]


def _query_audit_events(
    session,
    *,
    task_id: int | None = None,
    after_id: int | None = None,
    include_api_requests: bool = False,
    include_chat: bool = False,
):
    query = session.query(AuditEvent)
    if task_id is not None:
        query = query.filter(AuditEvent.task_id == task_id)
    if after_id is not None:
        query = query.filter(AuditEvent.id > after_id)
    if not include_api_requests:
        query = query.filter(AuditEvent.event_type != "api_request")
    if not include_chat:
        query = query.filter(~AuditEvent.event_type.in_(tuple(CHAT_EVENT_TYPES)))
    return query


def _normalize_audit_event(event: AuditEvent) -> dict:
    payload = _safe_payload(event.payload_json)
    return {
        "id": event.id,
        "task_id": event.task_id,
        "mission_id": event.task_id,
        "event_type": event.event_type,
        "label": _event_label(event.event_type),
        "note": _event_note(event.event_type, payload),
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "severity": _event_severity(event.event_type, payload),
        "status_after": _event_status_after(event.event_type, payload),
    }


def _iso_ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        s = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


def _handoff_thread_note(payload: dict) -> str:
    raw = payload.get("summary")
    if isinstance(raw, list):
        return _safe_text("; ".join(str(x) for x in raw[:4]))
    if raw:
        return _safe_text(str(raw))[:500]
    return _safe_text(str(payload.get("document_title") or payload.get("next_action") or ""))


def _thread_item_sort_key(item: dict) -> tuple:
    ts = _iso_ts(item.get("created_at"))
    kind_pref = 0 if item.get("kind") == "handoff" else 1
    tail = item.get("id") or ""
    try:
        seq = int(str(tail).split("-")[-1])
    except ValueError:
        seq = 0
    return (ts, kind_pref, seq)


def _build_unified_mission_thread(session, task_id: int, *, limit: int = 200) -> list[dict]:
    """Единая хронология: audit (включая чат) + handoffs — один контур для Telegram и Dashboard."""
    limit = max(1, min(int(limit), 500))
    audit_rows = (
        session.query(AuditEvent)
        .filter(AuditEvent.task_id == task_id, AuditEvent.event_type != "api_request")
        .order_by(AuditEvent.id.asc())
        .all()
    )
    handoff_rows = session.query(Handoff).filter(Handoff.task_id == task_id).order_by(Handoff.id.asc()).all()

    items: list[dict] = []
    for row in audit_rows:
        payload = _safe_payload(row.payload_json)
        kind = "chat" if row.event_type in CHAT_EVENT_TYPES else "audit"
        created = row.created_at.isoformat() if row.created_at else None
        label = _event_label(row.event_type)
        note = _event_note(row.event_type, payload)
        items.append(
            {
                "kind": kind,
                "id": f"audit-{row.id}",
                "mission_id": task_id,
                "audit_id": row.id,
                "event_type": row.event_type,
                "label": label,
                "note": note,
                "created_at": created,
                "severity": _event_severity(row.event_type, payload),
            }
        )

    for h in handoff_rows:
        payload = _safe_payload(h.payload_json or {})
        created = h.created_at.isoformat() if h.created_at else None
        items.append(
            {
                "kind": "handoff",
                "id": f"handoff-{h.id}",
                "mission_id": task_id,
                "handoff_id": h.id,
                "step_name": h.step_name,
                "step_index": h.step_index,
                "md_path": h.md_path,
                "label": f"Handoff · {h.step_name}",
                "note": _handoff_thread_note(payload),
                "created_at": created,
            }
        )

    items.sort(key=_thread_item_sort_key)
    if len(items) > limit:
        items = items[-limit:]
    return items


def _mission_thread_payload(task_id: int, limit: int) -> dict:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        if not repo.get_task(task_id):
            raise HTTPException(status_code=404, detail="Mission not found")
        items = _build_unified_mission_thread(session, task_id, limit=limit)
        return {
            "mission": _unified_mission_bundle(task_id),
            "items": items,
            "count": len(items),
        }


def _list_live_events(session, *, task_id: int | None = None, after_id: int | None = None, limit: int = DEFAULT_EVENT_LIMIT) -> list[dict]:
    limit = max(1, min(limit, MAX_EVENT_LIMIT))
    query = _query_audit_events(session, task_id=task_id, after_id=after_id)
    if after_id is not None:
        rows = query.order_by(AuditEvent.id.asc()).limit(limit).all()
    else:
        rows = list(reversed(query.order_by(AuditEvent.id.desc()).limit(limit).all()))
    return [_normalize_audit_event(row) for row in rows]


def _last_live_event_id(session, *, task_id: int | None = None) -> int:
    row = _query_audit_events(session, task_id=task_id).order_by(AuditEvent.id.desc()).first()
    return row.id if row else 0


def _build_task_timeline(task, logs: list[dict]) -> list[dict]:
    timeline = []
    if task.created_at:
        timeline.append(
            {
                "kind": "status",
                "title": "Новая задача",
                "status": "NEW",
                "created_at": task.created_at.isoformat(),
                "note": "Миссия зарегистрирована в системе.",
            }
        )

    for event in logs:
        event_type = event.get("event_type") or ""
        if event_type == "api_request" or event_type in CHAT_EVENT_TYPES:
            continue
        timeline.append(
            {
                "kind": "event",
                "title": _event_label(event_type),
                "status": event.get("status_after"),
                "created_at": event.get("created_at"),
                "note": _event_note(event_type, event.get("payload") or {}),
            }
        )

    if task.updated_at and task.status != "NEW":
        timeline.append(
            {
                "kind": "status",
                "title": "Текущий статус",
                "status": task.status,
                "created_at": task.updated_at.isoformat(),
                "note": f"Система находится в фазе {task.status}.",
            }
        )

    timeline.sort(key=lambda item: item.get("created_at") or "")
    return timeline


def _persona_for_step(step_name: str) -> dict:
    return {"code": step_name, **STEP_PERSONAS.get(step_name, {"label": step_name, "zone": "worklane", "animation": "think"})}


class OwnerOverrideBody(BaseModel):
    target_scope: str = Field(..., max_length=64)
    target_id: str = Field(..., max_length=128)
    override_text: str = Field(..., max_length=8000)
    valid_until: str | None = Field(default=None, description="ISO8601, опционально")


class ExplorationSelectBody(BaseModel):
    task_id: int = Field(..., ge=1)
    option_id: str = Field(..., min_length=1, max_length=64)
