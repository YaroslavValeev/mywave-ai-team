# Pydantic-контракты Smart Intake v0
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class IntakeAttachment(BaseModel):
    """Вложение после предобработки (фото/файл → описание)."""

    kind: str = Field(description="image|voice|file|other")
    description: str = Field(default="", description="Текст/caption/summary для классификатора")
    meta: dict[str, Any] = Field(default_factory=dict)


class ReplyContext(BaseModel):
    """Контекст ответа в треде (например reply в Telegram)."""

    task_id: int | None = None
    message_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizeIntakeRequest(BaseModel):
    text: str = ""
    attachments: list[IntakeAttachment] = Field(default_factory=list)
    source: str = "telegram"
    user_id: str = ""
    reply_context: ReplyContext | dict[str, Any] | None = None
    # v1: явная подсказка проекта (Dashboard / API)
    project_id_hint: int | None = None

    def reply_task_id(self) -> int | None:
        rc = self.reply_context
        if rc is None:
            return None
        if isinstance(rc, dict):
            tid = rc.get("task_id")
            if tid is not None:
                try:
                    return int(tid)
                except (TypeError, ValueError):
                    return None
            return None
        return rc.task_id


class TaskBrief(BaseModel):
    title: str = ""
    goal: str = ""
    input_summary: str = ""
    desired_outcome: str = ""
    constraints: list[str] = Field(default_factory=list)
    attachments: list[IntakeAttachment] = Field(default_factory=list)
    requires_owner_approval: bool = True
    # --- Smart Intake v1 (контекст / память) ---
    project_id: int | None = None
    project_name: str = ""
    related_task_id: int | None = None
    context_summary: str = ""
    memory_refs: list[str] = Field(default_factory=list)
    brief_confidence: float | None = Field(
        default=None,
        description="Уверенность резолвера проекта/задачи (0–1), не дублирует ответ confidence если None",
    )
    business_type: str | None = Field(default=None, description="product|marketing|revenue|ops")
    business_goal_hint: str = ""
    # Реальные продуктовые единицы MyWave (эвристика intake, не замена Project.slug)
    business_unit: str | None = Field(
        default=None,
        description="mywave|wakesafari|snowpolia|media|platform|training|generic",
    )


class BusinessAction(BaseModel):
    action_type: Literal["marketing", "product", "revenue", "ops"]
    expected_outcome: str = ""
    impact_level: Literal["low", "medium", "high"] = "low"
    time_to_value: str = ""
    requires_owner: bool = True


class ExecutionPack(BaseModel):
    action_title: str = ""
    why: str = ""
    ready_steps: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    how_to_execute: str = ""
    time_estimate: str = ""
    expected_result: str = ""
    pack_type: str = "generic_pack"


IntentType = Literal["task", "question", "analysis", "clarify", "noise"]
DecisionType = Literal["create", "clarify", "attach", "reject"]

ExecutionMode = Literal["quick", "light", "full"]
GMAction = Literal["answer", "create_task", "attach", "clarify", "reject"]
RiskLevel = Literal["low", "medium", "high"]


class GMDirectorDecision(BaseModel):
    """Решение GM/Director: как исполнять дальше (без запуска агентов здесь)."""

    execution_mode: ExecutionMode
    action: GMAction
    requires_approval: bool
    agents_plan: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    explanation: str = ""
    next_step: str = ""
    # Бизнес-слой: кратко «зачем это деньгам/росту» и что сделать после артефакта
    business_value_hint: str = ""
    next_business_step: str = ""
    # Autonomous Workflows: шаблон цепочки (engine не выбирает сам — только исполняет)
    workflow_template: str | None = None
    # Видимый владельцу тип работы (EVENT / REVENUE / …), см. app.dashboard.business_view
    owner_workstream: str = ""
    # Готовый execution pack для выполнения следующего бизнес-шага
    execution_pack: ExecutionPack | None = None


class NormalizeIntakeResponse(BaseModel):
    intent_type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    task_brief: TaskBrief = Field(default_factory=TaskBrief)
    needs_clarification: bool = False
    clarifying_questions: list[str] = Field(default_factory=list)
    decision: DecisionType
    # v1: трассировка резолвера (логи / API)
    matched_project_id: int | None = None
    matched_task_id: int | None = None
    similarity_score: float | None = None
    decision_reason: str = ""
    memory_used: bool = False
    # Owner Memory / Rules Layer
    owner_rule_keys_applied: list[str] = Field(default_factory=list)
    owner_explanation: str = ""
    owner_hard_block_intake: bool = False
    business_action: BusinessAction | None = None
    business_intent: bool = False
    # GM / Director Layer (после Owner Memory)
    gm_decision: GMDirectorDecision | None = None
