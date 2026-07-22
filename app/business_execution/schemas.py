from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionPack(BaseModel):
    action_title: str = ""
    why: str = ""
    ready_steps: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    how_to_execute: str = ""
    time_estimate: str = ""
    expected_result: str = ""
    pack_type: Literal[
        "offer_pack",
        "partner_outreach_pack",
        "content_pack",
        "landing_pack",
        "launch_plan_pack",
        "generic_pack",
    ] = "generic_pack"


class ExecutionContext(BaseModel):
    next_business_step: str = ""
    business_value_hint: str = ""
    owner_workstream: str = ""
    business_type: str = ""
    business_unit: str = ""
    workflow_template: str = ""
    expected_outcome: str = ""
    project_name: str = ""
    project_goal: str = ""
    project_stage: str = ""
    owner_text: str = ""
    task_id: int | None = None

    @classmethod
    def from_task(cls, task: Any, project: Any | None = None) -> "ExecutionContext":
        ba = getattr(task, "business_action_json", None) if task is not None else None
        ba = ba if isinstance(ba, dict) else {}
        gm = ba.get("gm_decision") if isinstance(ba.get("gm_decision"), dict) else {}
        return cls(
            next_business_step=str(gm.get("next_business_step") or ""),
            business_value_hint=str(gm.get("business_value_hint") or ""),
            owner_workstream=str(gm.get("owner_workstream") or ""),
            business_type=str(getattr(task, "business_type", "") or ""),
            business_unit=str(ba.get("business_unit") or ""),
            workflow_template=str(gm.get("workflow_template") or ""),
            expected_outcome=str((ba.get("expected_outcome") or getattr(task, "business_outcome", "") or "")),
            project_name=str(getattr(project, "name", "") or ""),
            project_goal=str(getattr(project, "business_goal", "") or ""),
            project_stage=str(getattr(project, "stage", "") or ""),
            owner_text=str(getattr(task, "owner_text", "") or ""),
            task_id=getattr(task, "id", None),
        )


def execution_pack_to_dict(pack: ExecutionPack | None) -> dict[str, Any] | None:
    return pack.model_dump() if pack else None
