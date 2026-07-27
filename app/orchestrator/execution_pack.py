"""Minimal post-approve EXECUTE pack (MEDIA outreach) — artifacts for Cursor/Owner, no auto-send."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts"))

_OUTREACH_TASK_TYPES = frozenset({"content_pipeline", "marketing_campaign", "marketing_plan"})
_OUTREACH_CLUSTERS = frozenset({"MEDIA", "MEDIA_OPS"})


def task_wants_outreach_execute(task: Any) -> bool:
    """True when approve should prepare a manual EXECUTE pack (not mass-send)."""
    if task is None:
        return False
    tt = str(getattr(task, "task_type", None) or "").strip().lower()
    if tt in _OUTREACH_TASK_TYPES:
        return True
    ba = getattr(task, "business_action_json", None) or {}
    if not isinstance(ba, dict):
        return False
    meta = ba.get("triage_meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    cluster = str(meta.get("agent_cluster") or ba.get("agent_cluster") or "").strip().upper()
    if cluster in _OUTREACH_CLUSTERS:
        return True
    # Handoff deliverable kind=message_draft
    for h in getattr(task, "handoffs", None) or []:
        payload = getattr(h, "payload_json", None) or {}
        if not isinstance(payload, dict):
            continue
        d = payload.get("deliverable")
        if isinstance(d, dict) and str(d.get("kind") or "") == "message_draft":
            return True
    return False


def _execution_dir(task_id: int) -> Path:
    return ARTIFACTS_DIR / "tasks" / f"task_{task_id}" / "execution"


def _deliverable_from_task(task: Any) -> Optional[dict]:
    for h in getattr(task, "handoffs", None) or []:
        payload = getattr(h, "payload_json", None) or {}
        if not isinstance(payload, dict):
            continue
        d = payload.get("deliverable")
        if isinstance(d, dict) and (d.get("body_lines") or d.get("kind")):
            return d
    return None


def _message_lines(task: Any) -> list[str]:
    """Always rebuild from content_intent so EXECUTE pack tracks current marketing copy.

    Stale handoff deliverable (PLAN-time) must not block YClients / USP updates.
    """
    from app.orchestrator.content_intent import build_content_outreach_draft

    draft = build_content_outreach_draft(getattr(task, "owner_text", None) or "")
    raw = list(draft.get("message_draft") or [])
    if raw:
        return [str(x).rstrip() for x in raw]
    deliverable = _deliverable_from_task(task)
    if deliverable:
        return [str(x).rstrip() for x in (deliverable.get("body_lines") or []) if str(x).strip()]
    return []


def _find_contacts_csv(task_id: int) -> Optional[Path]:
    """Prefer this task's CSV; else newest parsernews_*.csv under any task execution/."""
    exe = _execution_dir(task_id)
    preferred = [
        exe / "contacts_unique.csv",
        exe / "parsernews_outreach_contacts.csv",
    ]
    for p in preferred:
        if p.is_file():
            return p
    if exe.is_dir():
        local = sorted(exe.glob("parsernews_outreach_contacts_*.csv"), reverse=True)
        if local:
            return local[0]
    root = ARTIFACTS_DIR / "tasks"
    if not root.is_dir():
        return None
    candidates: list[Path] = []
    for path in root.glob("task_*/execution/parsernews_outreach_contacts_*.csv"):
        candidates.append(path)
    for path in root.glob("task_*/execution/contacts_unique.csv"):
        candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def prepare_outreach_execution_pack(
    repo: Any,
    task_id: int,
    *,
    source: str = "approve",
) -> dict[str, Any]:
    """Write EXECUTE_PACK.md + message_to_send.txt under task execution/. No network send.

    Returns dict with paths and flags. Idempotent overwrite of pack files.
    """
    task = repo.get_task(task_id)
    if not task:
        return {"ok": False, "reason": "task_not_found", "task_id": task_id}

    exe = _execution_dir(task_id)
    exe.mkdir(parents=True, exist_ok=True)

    message_lines = _message_lines(task)
    message_path = exe / "message_to_send.txt"
    message_path.write_text("\n".join(message_lines) + "\n", encoding="utf-8")

    contacts = _find_contacts_csv(task_id)
    contacts_note = str(contacts) if contacts else (
        "CSV ещё нет — положи contacts_unique.csv сюда или запусти "
        "scripts/export_parsernews_unique_emails.py и скопируй файл в execution/."
    )

    send_log = exe / "send_log.md"
    if not send_log.exists():
        send_log.write_text(
            "# send_log\n\n"
            "_Пока пусто. После ручной/Cursor рассылки допиши: дата, канал, число получателей, результат._\n",
            encoding="utf-8",
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pack_path = exe / "EXECUTE_PACK.md"
    pack_body = "\n".join(
        [
            f"# EXECUTE pack — task #{task_id}",
            "",
            f"- created_at_utc: `{now}`",
            f"- source: `{source}`",
            f"- task_type: `{getattr(task, 'task_type', None) or '—'}`",
            f"- status_hint: `EXECUTION_READY` (рассылка вручную / Cursor; AI-TEAM не шлёт сам)",
            "",
            "## Что делать Owner / Cursor",
            "",
            "1. Проверить текст в `message_to_send.txt`.",
            "2. Проверить сегмент контактов (не слать всем подряд).",
            f"3. Контакты: `{contacts_note}`",
            "4. Отправить **вручную** или согласованным tool (не боевой TG-бот AI-TEAM без отдельного GO).",
            "5. Записать итог в `send_log.md`.",
            "6. Закрыть миссию: `python scripts/prepare_outreach_execute.py --task-id "
            f"{task_id} --mark-done` (на RU в контейнере) или Dashboard/API DONE.",
            "",
            "## Текст сообщения (копия)",
            "",
            "```",
            *message_lines,
            "```",
            "",
            "## Запрещено без отдельного Owner GO",
            "",
            "- Массовая отправка из контейнера AI-TEAM",
            "- Публикация CSV с PII в git",
            "",
            "См. также: `docs/migration/EXECUTE_OUTREACH_CHECKLIST.md`",
            "",
        ]
    )
    pack_path.write_text(pack_body, encoding="utf-8")

    ba = dict(getattr(task, "business_action_json", None) or {})
    ba["execution_pack"] = {
        "kind": "outreach_manual",
        "prepared_at": now,
        "source": source,
        "pack_path": str(pack_path).replace("\\", "/"),
        "message_path": str(message_path).replace("\\", "/"),
        "contacts_path": str(contacts).replace("\\", "/") if contacts else None,
        "auto_send": False,
    }
    ba["execution_ready"] = True
    repo.update_task(task_id, business_action_json=ba)

    try:
        repo.add_audit_event(
            "EXECUTION_PACK_PREPARED",
            task_id=task_id,
            payload={
                "kind": "outreach_manual",
                "pack_path": ba["execution_pack"]["pack_path"],
                "source": source,
                "has_contacts": bool(contacts),
            },
        )
    except Exception:
        logger.exception("audit EXECUTION_PACK_PREPARED failed task_id=%s", task_id)

    logger.info(
        "EXECUTION_PACK_PREPARED task_id=%s pack=%s contacts=%s",
        task_id,
        pack_path,
        bool(contacts),
    )
    return {
        "ok": True,
        "task_id": task_id,
        "pack_path": str(pack_path),
        "message_path": str(message_path),
        "contacts_path": str(contacts) if contacts else None,
        "execution_dir": str(exe),
        "auto_send": False,
    }


def resolve_status_after_approve(task: Any, *, has_pr: bool) -> str:
    """Approve without PR: outreach → EXECUTION_READY; else DONE."""
    if has_pr:
        return "APPROVED_WAIT_MERGE"
    if task_wants_outreach_execute(task):
        return "EXECUTION_READY"
    return "DONE"
