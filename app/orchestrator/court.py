# app/orchestrator/court.py — финальный отчёт .md
import os
from pathlib import Path
from typing import Optional

from app.config import get_policy
from app.shared.redaction import redact


ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts"))


def run_court(
    task_id: int,
    triage_result: dict,
    pipeline_result: dict,
    roundtable_result: dict,
    repo,
) -> dict:
    """
    Генерирует финальный отчёт .md и short summary.
    """
    task = repo.get_task(task_id)
    if not task:
        return {"report_path": None, "summary": "Task not found"}

    max_chars = get_policy().get("limits", {}).get("telegram_summary_max_chars", 1200)

    report_lines = [
        "# AGM Final Report",
        "",
        f"**Task #{task_id}**",
        "",
        "## Executive Summary",
        f"Domain: {triage_result.get('domain', 'N/A')} | Type: {triage_result.get('task_type', 'N/A')} | Criticality: {triage_result.get('criticality', 'N/A')}",
        "",
        "## Deliverables",
        "- Pipeline completed",
        "- Roundtable review done",
        "- Awaiting Owner approval if EXECUTE",
        "",
        "## Acceptance Checklist",
        "- [ ] Owner approved (if CRITICAL EXECUTE)",
        "- [ ] Artifacts reviewed",
        "",
        "## Key Decisions",
        "- Proceed with standard flow",
        "",
        "## Risks & Mitigations",
    ]

    for r in roundtable_result.get("risk_table", []):
        report_lines.append(f"- **{r.get('issue', '')}**: {r.get('recommendation', '')} (Owner approval: {r.get('owner_approval_needed', False)})")

    report_lines.extend([
        "",
        "## Next Actions",
        "- Owner: Approve / Rework / Clarify",
        "",
    ])

    report_content = redact("\n".join(report_lines))
    reports_path = ARTIFACTS_DIR / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    report_path = reports_path / f"task_{task_id}_report.md"
    report_path.write_text(report_content, encoding="utf-8")

    summary = redact(
        f"Task #{task_id} готов. Domain: {triage_result.get('domain', 'N/A')}, "
        f"Type: {triage_result.get('task_type', 'N/A')}. "
        "Отчёт сохранён. Требуется Approve для EXECUTE."
    )[:max_chars]

    repo.update_task(task_id, report_path=str(report_path), summary=summary)

    return {"report_path": str(report_path), "summary": summary}
