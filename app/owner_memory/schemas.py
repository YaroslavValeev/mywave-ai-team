# Pydantic: контексты и результаты Owner Rules Engine
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OwnerRuleItemPublic(BaseModel):
    id: int
    kind: str
    item_key: str
    text: str
    tier: str
    scope: str
    strength: float
    weight: float
    priority_rank: int


class OwnerRulesBundle(BaseModel):
    owner_key: str
    rules: list[OwnerRuleItemPublic] = Field(default_factory=list)
    preferences: list[OwnerRuleItemPublic] = Field(default_factory=list)
    priorities: list[OwnerRuleItemPublic] = Field(default_factory=list)
    overrides: list[dict[str, Any]] = Field(default_factory=list)


class IntakeRuleContext(BaseModel):
    decision: str
    confidence: float
    needs_clarification: bool
    decision_reason: str = ""
    matched_project_id: int | None = None


class ExecutionRuleContext(BaseModel):
    plan_or_execute: str = ""
    domain: str = ""
    task_type: str = ""
    execute_gate: str = ""
    flags: dict[str, bool] = Field(default_factory=dict)
    needs_approval_base: bool = False
    task_id: int | None = None


class OwnerRuleEngineResult(BaseModel):
    hard_blocks: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    decision_adjustments: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    item_ids_applied: list[int] = Field(default_factory=list)
    item_keys_applied: list[str] = Field(default_factory=list)
    requires_wait_owner: bool = False


DecisionAdjustment = Literal[
    "prefer_clarify_over_autocreate",
    "set_requires_approval_true",
]
