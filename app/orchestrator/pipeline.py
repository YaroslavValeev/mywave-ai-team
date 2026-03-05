# app/orchestrator/pipeline.py — config-driven шаги, Handoff
import json
import os
from pathlib import Path
from typing import Optional

from app.config import get_routing
from app.shared.redaction import redact


ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts"))


def run_pipeline(task_id: int, triage_result: dict, repo) -> dict:
    """
    Выполняет pipeline из routing.yaml.
    Каждый шаг пишет Handoff (json + краткий md).
    """
    routing = get_routing()
    domain = triage_result.get("domain", "PRODUCT_DEV")
    task_type = triage_result.get("task_type", "feature_delivery")

    domains_cfg = routing.get("domains", {})
    pipeline_steps = []
    if domain in domains_cfg:
        task_types_cfg = domains_cfg[domain].get("task_types", {})
        if task_type in task_types_cfg:
            pipeline_steps = task_types_cfg[task_type].get("pipeline", ["PM", "ARCH"])

    if not pipeline_steps:
        pipeline_steps = ["PM", "ARCH"]

    handoffs = []
    for i, step_name in enumerate(pipeline_steps):
        payload = {
            "summary": [f"Step {i+1}: {step_name} completed"],
            "artifacts": [],
            "decisions": [f"Proceed to next step"],
            "assumptions": [],
            "risks": [],
            "open_questions": [],
            "next_action": pipeline_steps[i + 1] if i + 1 < len(pipeline_steps) else "Roundtable",
        }
        md_content = redact(_handoff_to_md(step_name, payload))
        artifacts_path = ARTIFACTS_DIR / "handoffs"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        md_path = artifacts_path / f"task_{task_id}_step_{i}.md"
        md_path.write_text(md_content, encoding="utf-8")

        repo.add_handoff(
            task_id=task_id,
            step_index=i,
            step_name=step_name,
            payload=payload,
            md_path=str(md_path),
        )
        handoffs.append({"step": step_name, "payload": payload, "md_path": str(md_path)})

    return {"handoffs": handoffs}


def _handoff_to_md(step_name: str, payload: dict) -> str:
    lines = [f"# Handoff: {step_name}", ""]
    for k, v in payload.items():
        if isinstance(v, list):
            lines.append(f"## {k}")
            for item in v:
                lines.append(f"- {item}")
        else:
            lines.append(f"## {k}\n{v}")
        lines.append("")
    return "\n".join(lines)
